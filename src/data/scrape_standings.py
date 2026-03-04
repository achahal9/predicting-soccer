"""
League standings scraper.

Scrapes current league table positions from FBref.com using requests + BeautifulSoup.

Usage:
    python -m src.data.scrape_standings              # Scrape all leagues
    python -m src.data.scrape_standings --league E0   # PL only
"""

import sqlite3
import time
import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
from datetime import date

from src.data.scraper_utils import (
    LEAGUE_CONFIG,
    normalize_team_name,
    get_or_create_team,
    get_current_season_year,
    ScrapingResult,
)

logger = logging.getLogger(__name__)

FBREF_DELAY = 4.0

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch and parse a page from FBref."""
    try:
        logger.info(f"Fetching: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def scrape_league_standings(
    league_code: str,
    season_year: Optional[int] = None
) -> ScrapingResult:
    """
    Scrape current league standings from FBref.
    
    Args:
        league_code: Division code (e.g. 'E0')
        season_year: Season start year (default: current)
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
    soup = _fetch_page(url)
    
    if soup is None:
        result.errors.append("Failed to fetch page")
        return result
    
    try:
        # Find standings table
        table = None
        for t in soup.find_all('table', class_='stats_table'):
            caption = t.find('caption')
            if caption and ('Overall' in caption.get_text() or 'Regular' in caption.get_text()):
                table = t
                break
        
        if table is None:
            tables = soup.find_all('table', class_='stats_table')
            if tables:
                table = tables[0]
        
        if table is None:
            result.errors.append("Could not find standings table")
            return result
        
        tbody = table.find('tbody')
        if tbody is None:
            result.errors.append("No tbody in standings table")
            return result
        
        for row in tbody.find_all('tr'):
            if row.find('th', colspan=True):
                continue
            
            # Position
            rank_cell = row.find(['td', 'th'], attrs={'data-stat': 'rank'})
            pos = rank_cell.get_text(strip=True) if rank_cell else '0'
            
            # Team name
            team_cell = (
                row.find(['td', 'th'], attrs={'data-stat': 'team'}) or
                row.find(['td', 'th'], attrs={'data-stat': 'squad'})
            )
            if team_cell is None:
                continue
            
            team_link = team_cell.find('a')
            team_name_raw = team_link.get_text(strip=True) if team_link else team_cell.get_text(strip=True)
            if not team_name_raw:
                continue
            
            team_name = normalize_team_name(team_name_raw)
            
            standing = {
                'team': team_name,
                'league_code': league_code,
                'season_year': season_year,
                'position': _parse_int(pos),
                'played': _get_stat_int(row, 'games'),
                'wins': _get_stat_int(row, 'wins'),
                'draws': _get_stat_int(row, 'ties'),
                'losses': _get_stat_int(row, 'losses'),
                'goals_for': _get_stat_int(row, 'goals_scored'),
                'goals_against': _get_stat_int(row, 'goals_against'),
                'goal_diff': _get_stat_int(row, 'goal_diff'),
                'points': _get_stat_int(row, 'points'),
            }
            
            result.data.append(standing)
        
        if result.data:
            result.success = True
            logger.info(f"Scraped {len(result.data)} standings for {config['name']}")
        else:
            result.errors.append("No standings rows parsed")
    
    except Exception as e:
        result.errors.append(f"Parse error: {e}")
        logger.error(f"Error parsing standings for {league_code}: {e}")
    
    return result


def save_standings(
    conn: sqlite3.Connection,
    league_code: str,
    standings: List[Dict],
    snapshot_date: Optional[str] = None
) -> int:
    """Save standings snapshot to the database."""
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()
    
    cursor = conn.cursor()
    count = 0
    
    for s in standings:
        team_id = get_or_create_team(conn, s['team'])
        season_code = f"{s['season_year'] % 100:02d}{(s['season_year'] + 1) % 100:02d}"
        
        cursor.execute('''
            INSERT INTO standings
            (team_id, season, league, position, played, wins, draws, losses,
             goals_for, goals_against, goal_diff, points, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, season, league, snapshot_date)
            DO UPDATE SET
                position = excluded.position,
                played = excluded.played,
                wins = excluded.wins,
                draws = excluded.draws,
                losses = excluded.losses,
                goals_for = excluded.goals_for,
                goals_against = excluded.goals_against,
                goal_diff = excluded.goal_diff,
                points = excluded.points
        ''', (
            team_id, season_code, league_code,
            s.get('position', 0),
            s.get('played', 0),
            s.get('wins', 0),
            s.get('draws', 0),
            s.get('losses', 0),
            s.get('goals_for', 0),
            s.get('goals_against', 0),
            s.get('goal_diff', 0),
            s.get('points', 0),
            snapshot_date,
        ))
        count += 1
    
    conn.commit()
    return count


def scrape_all_standings(
    conn: sqlite3.Connection,
    leagues: Optional[List[str]] = None,
    season_year: Optional[int] = None
) -> ScrapingResult:
    """Scrape and save standings for all specified leagues."""
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())
    
    overall = ScrapingResult(success=True)
    
    for i, league_code in enumerate(leagues):
        if i > 0:
            time.sleep(FBREF_DELAY)
        
        result = scrape_league_standings(league_code, season_year)
        
        if result.success and result.data:
            saved = save_standings(conn, league_code, result.data)
            overall.records_inserted += saved
            overall.data.extend(result.data)
            logger.info(f"  → {saved} standings saved for {league_code}")
        else:
            overall.errors.extend(result.errors)
            logger.warning(f"  → Failed for {league_code}: {result.errors}")
    
    if overall.errors:
        overall.success = len(overall.data) > 0
    
    logger.info(f"Standings scraping complete: {overall}")
    return overall


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_stat_int(row, stat_name: str) -> int:
    cell = row.find('td', attrs={'data-stat': stat_name})
    if cell is None:
        return 0
    text = cell.get_text(strip=True).replace(',', '').replace('+', '').replace('−', '-')
    try:
        return int(text)
    except (ValueError, AttributeError):
        return 0


def _parse_int(value: Optional[str]) -> int:
    if not value:
        return 0
    try:
        return int(value.strip().replace(',', '').replace('+', '').replace('−', '-'))
    except (ValueError, AttributeError):
        return 0


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description='Scrape league standings from FBref')
    parser.add_argument('--league', type=str, help='Single league code (e.g. E0)')
    parser.add_argument('--season', type=int, help='Season start year (e.g. 2025)')
    parser.add_argument('--dry-run', action='store_true', help='Print without saving to DB')
    args = parser.parse_args()
    
    leagues = [args.league] if args.league else None
    
    if args.dry_run:
        for lc in (leagues or list(LEAGUE_CONFIG.keys())):
            result = scrape_league_standings(lc, args.season)
            name = LEAGUE_CONFIG[lc]['name']
            print(f"\n{'='*50}")
            print(f" {name} Standings")
            print(f"{'='*50}")
            print(f"{'Pos':<4} {'Team':<25} {'P':<4} {'W':<4} {'D':<4} {'L':<4} {'GD':<5} {'Pts':<4}")
            print('-' * 50)
            for s in result.data:
                print(f"{s['position']:<4} {s['team']:<25} {s['played']:<4} "
                      f"{s['wins']:<4} {s['draws']:<4} {s['losses']:<4} "
                      f"{s['goal_diff']:<5} {s['points']:<4}")
            if result.errors:
                print(f"Errors: {result.errors}")
            if lc != (leagues or list(LEAGUE_CONFIG.keys()))[-1]:
                time.sleep(FBREF_DELAY)
    else:
        conn = sqlite3.connect('sports_data.db')
        result = scrape_all_standings(conn, leagues, args.season)
        print(result)
        conn.close()
