"""
FBref advanced stats scraper.

Scrapes team-level xG, possession, shots, and other advanced stats
from FBref.com for all 5 leagues using requests + BeautifulSoup.

Usage:
    python -m src.data.scrape_fbref_stats          # Scrape all leagues
    python -m src.data.scrape_fbref_stats --league E0  # Scrape PL only
"""

import sqlite3
import time
import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict

from src.data.scraper_utils import (
    LEAGUE_CONFIG,
    normalize_team_name,
    get_or_create_team,
    get_current_season_year,
    ScrapingResult,
)

logger = logging.getLogger(__name__)

# Inter-request delay for FBref (they enforce ~3s rate limit)
FBREF_DELAY = 4.0

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _fetch_fbref_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch and parse a page from FBref."""
    try:
        logger.info(f"Fetching FBref: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def scrape_league_stats(
    league_code: str,
    season_year: Optional[int] = None
) -> ScrapingResult:
    """
    Scrape team-level stats for a league from FBref.
    
    Args:
        league_code: Division code (e.g. 'E0' for Premier League)
        season_year: Start year of season (e.g. 2025 for 2025-26).
    """
    config = LEAGUE_CONFIG.get(league_code)
    if not config:
        return ScrapingResult(success=False, errors=[f"Unknown league: {league_code}"])
    
    if season_year is None:
        season_year = get_current_season_year()
    
    fbref_id = config['fbref_id']
    fbref_slug = config['fbref_slug']
    url = f"https://fbref.com/en/comps/{fbref_id}/{season_year}-{season_year + 1}/{fbref_slug}-Stats"
    
    result = ScrapingResult(source_url=url)
    soup = _fetch_fbref_page(url)
    
    if soup is None:
        result.errors.append("Failed to fetch page")
        return result
    
    try:
        # Find the overall stats table — FBref uses table with id pattern
        table = None
        for t in soup.find_all('table', class_='stats_table'):
            caption = t.find('caption')
            if caption and 'Overall' in caption.get_text():
                table = t
                break
        
        if table is None:
            # Fallback: first stats_table
            tables = soup.find_all('table', class_='stats_table')
            if tables:
                table = tables[0]
        
        if table is None:
            result.errors.append("Could not find stats table on page")
            return result
        
        tbody = table.find('tbody')
        if tbody is None:
            result.errors.append("No tbody in stats table")
            return result
        
        for row in tbody.find_all('tr'):
            # Skip spacer rows
            if row.find('th', colspan=True):
                continue
            
            # Team name
            team_cell = row.find(['td', 'th'], attrs={'data-stat': 'team'})
            if team_cell is None:
                team_cell = row.find(['td', 'th'], attrs={'data-stat': 'squad'})
            
            if team_cell is None:
                continue
            
            team_link = team_cell.find('a')
            team_name_raw = team_link.get_text(strip=True) if team_link else team_cell.get_text(strip=True)
            
            if not team_name_raw:
                continue
            
            team_name = normalize_team_name(team_name_raw)
            
            stats = {
                'team': team_name,
                'league_code': league_code,
                'season_year': season_year,
                'matches_played': _get_stat_int(row, 'games'),
                'wins': _get_stat_int(row, 'wins'),
                'draws': _get_stat_int(row, 'ties'),
                'losses': _get_stat_int(row, 'losses'),
                'goals_for': _get_stat_int(row, 'goals_scored'),
                'goals_against': _get_stat_int(row, 'goals_against'),
                'xg': _get_stat_float(row, 'xg_for') or _get_stat_float(row, 'xg'),
                'xga': _get_stat_float(row, 'xg_against') or _get_stat_float(row, 'xga'),
                'possession': _get_stat_float(row, 'possession'),
                'points': _get_stat_int(row, 'points'),
            }
            
            result.data.append(stats)
        
        if result.data:
            result.success = True
            logger.info(f"Scraped {len(result.data)} teams for {config['name']}")
        else:
            result.errors.append("No team rows found in table")
    
    except Exception as e:
        result.errors.append(f"Parse error: {e}")
        logger.error(f"Error parsing FBref stats for {league_code}: {e}")
    
    return result


def upsert_team_stats(
    conn: sqlite3.Connection,
    league_code: str,
    stats_list: List[Dict]
) -> int:
    """Upsert scraped team stats into the team_stats table."""
    cursor = conn.cursor()
    count = 0
    
    for stats in stats_list:
        team_id = get_or_create_team(conn, stats['team'])
        season_code = f"{stats['season_year'] % 100:02d}{(stats['season_year'] + 1) % 100:02d}"
        
        cursor.execute('''
            INSERT INTO team_stats 
            (team_id, season, league, apps, wins, draws, losses,
             goals_for, goals_against, expected_goals, expected_goals_against,
             possession_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, season, league) 
            DO UPDATE SET
                apps = excluded.apps,
                wins = excluded.wins,
                draws = excluded.draws,
                losses = excluded.losses,
                goals_for = excluded.goals_for,
                goals_against = excluded.goals_against,
                expected_goals = excluded.expected_goals,
                expected_goals_against = excluded.expected_goals_against,
                possession_percent = excluded.possession_percent
        ''', (
            team_id, season_code, league_code,
            stats.get('matches_played', 0),
            stats.get('wins', 0),
            stats.get('draws', 0),
            stats.get('losses', 0),
            stats.get('goals_for', 0),
            stats.get('goals_against', 0),
            stats.get('xg', 0.0),
            stats.get('xga', 0.0),
            stats.get('possession'),
        ))
        count += 1
    
    conn.commit()
    return count


def scrape_fbref_advanced_stats(
    conn: sqlite3.Connection,
    leagues: Optional[List[str]] = None,
    season_year: Optional[int] = None
) -> ScrapingResult:
    """Main entry point: scrape FBref stats for all specified leagues."""
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())
    
    overall_result = ScrapingResult(success=True)
    
    for i, league_code in enumerate(leagues):
        if i > 0:
            logger.debug(f"Rate limiting: waiting {FBREF_DELAY}s")
            time.sleep(FBREF_DELAY)
        
        result = scrape_league_stats(league_code, season_year)
        
        if result.success and result.data:
            inserted = upsert_team_stats(conn, league_code, result.data)
            overall_result.records_inserted += inserted
            overall_result.data.extend(result.data)
            logger.info(f"  → {inserted} team stats upserted for {league_code}")
        else:
            overall_result.errors.extend(result.errors)
            logger.warning(f"  → Failed for {league_code}: {result.errors}")
    
    if overall_result.errors:
        overall_result.success = len(overall_result.data) > 0
    
    logger.info(f"FBref scraping complete: {overall_result}")
    return overall_result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_stat_int(row, stat_name: str) -> int:
    cell = row.find('td', attrs={'data-stat': stat_name})
    if cell is None:
        return 0
    text = cell.get_text(strip=True).replace(',', '')
    try:
        return int(text)
    except (ValueError, AttributeError):
        return 0


def _get_stat_float(row, stat_name: str) -> float:
    cell = row.find('td', attrs={'data-stat': stat_name})
    if cell is None:
        return 0.0
    text = cell.get_text(strip=True).replace(',', '')
    try:
        return float(text)
    except (ValueError, AttributeError):
        return 0.0


def _parse_int(value: Optional[str]) -> int:
    if not value:
        return 0
    try:
        return int(value.strip().replace(',', ''))
    except (ValueError, AttributeError):
        return 0


def _parse_float(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return float(value.strip().replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description='Scrape FBref advanced team stats')
    parser.add_argument('--league', type=str, help='Single league code (e.g. E0)')
    parser.add_argument('--season', type=int, help='Season start year (e.g. 2025)')
    parser.add_argument('--dry-run', action='store_true', help='Print results without writing to DB')
    args = parser.parse_args()
    
    leagues = [args.league] if args.league else None
    
    if args.dry_run:
        for lc in (leagues or list(LEAGUE_CONFIG.keys())):
            result = scrape_league_stats(lc, args.season)
            print(f"\n{LEAGUE_CONFIG[lc]['name']}:")
            for team in result.data:
                print(f"  {team['team']}: xG={team['xg']}, xGA={team['xga']}, poss={team['possession']}%")
            if result.errors:
                print(f"  Errors: {result.errors}")
            if lc != (leagues or list(LEAGUE_CONFIG.keys()))[-1]:
                time.sleep(FBREF_DELAY)
    else:
        conn = sqlite3.connect('sports_data.db')
        result = scrape_fbref_advanced_stats(conn, leagues, args.season)
        print(result)
        conn.close()
