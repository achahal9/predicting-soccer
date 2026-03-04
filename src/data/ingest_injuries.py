"""
Injury data ingestion module.

Sources:
- Transfermarkt (via Playwright): https://www.transfermarkt.com/ injury lists
- Provides: injury type, expected return date, current status

This module fetches injury data and maintains a history of player availability.
"""

import sqlite3
from datetime import datetime
import pandas as pd
import time
import logging
from bs4 import BeautifulSoup
from typing import Optional, Dict, List

from src.data.scraper_utils import (
    LEAGUE_CONFIG,
    normalize_team_name,
    get_or_create_team,
    create_player_if_needed,
    fuzzy_match_player,
    ScrapingResult,
    get_current_season_year,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Delay between Transfermarkt requests
TM_DELAY = 5.0


def add_injury_record(
    conn: sqlite3.Connection,
    player_id: int,
    injury_date: str,
    injury_type: str,
    expected_return_date: Optional[str] = None,
    status: str = 'out',
    severity: str = 'moderate',
    team_id: Optional[int] = None,
    source: str = 'transfermarkt'
) -> int:
    """
    Add an injury record for a player.
    
    Args:
        conn: Database connection
        player_id: Master player ID
        injury_date: Date of injury (YYYY-MM-DD)
        injury_type: Type of injury (e.g., 'hamstring', 'ligament', 'fracture')
        expected_return_date: Expected return date (YYYY-MM-DD)
        status: 'out', 'doubt', or 'available'
        severity: 'minor', 'moderate', 'severe'
        team_id: Team ID (optional)
        source: Data source (default: transfermarkt)
    
    Returns:
        injury_id of the inserted record
    """
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO injury_records
        (player_id, team_id, injury_date, injury_type, expected_return_date, 
         status, severity, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (player_id, team_id, injury_date, injury_type, expected_return_date,
          status, severity, source, datetime.now()))
    conn.commit()
    return cursor.lastrowid

def update_injury_status(
    conn: sqlite3.Connection,
    injury_id: int,
    status: str,
    actual_return_date: Optional[str] = None
):
    """Update injury status and return date."""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE injury_records 
        SET status = ?, actual_return_date = ?
        WHERE injury_id = ?
    ''', (status, actual_return_date, injury_id))
    conn.commit()

def get_player_injuries(
    conn: sqlite3.Connection,
    player_id: int,
    as_of_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Get all injuries for a player.
    
    Args:
        conn: Database connection
        player_id: Master player ID
        as_of_date: Filter to injuries as of this date (YYYY-MM-DD)
    
    Returns:
        DataFrame of injury records
    """
    query = 'SELECT * FROM injury_records WHERE player_id = ?'
    params = [player_id]
    
    if as_of_date:
        query += ' AND injury_date <= ?'
        params.append(as_of_date)
    
    query += ' ORDER BY injury_date DESC'
    return pd.read_sql_query(query, conn, params=params)

def get_team_injuries(
    conn: sqlite3.Connection,
    team_id: int,
    as_of_date: Optional[str] = None,
    status_filter: Optional[str] = None
) -> pd.DataFrame:
    """
    Get all current injuries for a team.
    
    Args:
        conn: Database connection
        team_id: Team ID
        as_of_date: As of specific date (YYYY-MM-DD)
        status_filter: Filter by 'out', 'doubt', 'available'
    
    Returns:
        DataFrame of injury records
    """
    query = '''
        SELECT ir.*, p.full_name, p.position
        FROM injury_records ir
        JOIN players p ON ir.player_id = p.master_id
        WHERE ir.team_id = ?
    '''
    params = [team_id]
    
    if as_of_date:
        query += ' AND ir.injury_date <= ?'
        params.append(as_of_date)
    
    if status_filter:
        query += ' AND ir.status = ?'
        params.append(status_filter)
    else:
        # Default: show only active injuries (not returned)
        query += " AND ir.status IN ('out', 'doubt')"
    
    query += ' ORDER BY ir.injury_date DESC'
    return pd.read_sql_query(query, conn, params=params)

def calculate_injury_impact(conn: sqlite3.Connection, team_id: int, as_of_date: str) -> Dict:
    """
    Calculate a team's injury impact (missing key players).
    
    Returns a dict with:
        - total_injured: count of injured players
        - out_players: list of injured player names
        - impact_score: 0-1 score of injury severity
    """
    injuries = get_team_injuries(conn, team_id, as_of_date, status_filter='out')
    
    # Get team roster stats to weight importance
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as total_apps FROM player_stats
        WHERE team_id = ? AND season = ?
    ''', (team_id, as_of_date.split('-')[0]))
    
    return {
        'total_injured': len(injuries),
        'out_players': injuries['full_name'].tolist() if len(injuries) > 0 else [],
        'impact_score': min(len(injuries) / 11.0, 1.0)  # Max 11 players, normalized
    }


# ─── Transfermarkt Scraper (Real Implementation) ─────────────────────────────

def _fetch_tm_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a Transfermarkt page using Playwright (Cloudflare bypass)."""
    # Try Playwright first
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info(f"Fetching Transfermarkt (Playwright): {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            )
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
        
        return BeautifulSoup(html, 'html.parser')
    except ImportError:
        logger.warning("Playwright not installed, falling back to requests")
    except Exception as e:
        logger.warning(f"Playwright failed ({e}), falling back to requests")
    
    # Fallback: requests
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def _classify_severity(injury_type: str) -> str:
    """Classify injury severity based on type description."""
    if not injury_type:
        return 'moderate'
    
    injury_lower = injury_type.lower()
    
    severe_keywords = [
        'cruciate', 'acl', 'mcl', 'fracture', 'broken', 'torn',
        'rupture', 'surgery', 'achilles', 'meniscus'
    ]
    minor_keywords = [
        'bruise', 'knock', 'illness', 'flu', 'cold', 'dead leg',
        'cramp', 'fatigue', 'precaution', 'rest'
    ]
    
    for kw in severe_keywords:
        if kw in injury_lower:
            return 'severe'
    for kw in minor_keywords:
        if kw in injury_lower:
            return 'minor'
    
    return 'moderate'


def _parse_tm_date(date_text: str) -> Optional[str]:
    """Parse Transfermarkt date formats to YYYY-MM-DD."""
    if not date_text:
        return None
    
    date_text = date_text.strip()
    if date_text in ('-', '?', 'N/A', ''):
        return None
    
    # Try common TM date formats
    for fmt in ('%b %d, %Y', '%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d', '%b %Y'):
        try:
            return datetime.strptime(date_text, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None


def scrape_league_injuries(
    league_code: str,
) -> ScrapingResult:
    """
    Scrape all current injuries for a league from Transfermarkt.
    
    Uses the league-level injury page which shows all injuries at once.
    
    Args:
        league_code: Division code (e.g. 'E0')
    
    Returns:
        ScrapingResult with injury data
    """
    config = LEAGUE_CONFIG.get(league_code)
    if not config:
        return ScrapingResult(success=False, errors=[f"Unknown league: {league_code}"])
    
    tm_id = config['tm_id']
    tm_slug = config['tm_slug']
    
    url = f"https://www.transfermarkt.com/{tm_slug}/verletzungen/wettbewerb/{tm_id}"
    
    result = ScrapingResult(source_url=url)
    soup = _fetch_tm_page(url)
    
    if soup is None:
        result.errors.append("Failed to fetch Transfermarkt page")
        return result
    
    try:
        # Transfermarkt injury pages have a main table with class 'items'
        tables = soup.find_all('table', class_='items')
        
        if not tables:
            tables_resp = soup.find_all('div', class_='responsive-table')
            for div in tables_resp:
                t = div.find('table')
                if t:
                    tables.append(t)
        
        if not tables:
            result.errors.append("No injury tables found on page")
            _try_alternative_injury_parse(soup, result, league_code)
            return result
        
        for table in tables:
            tbody = table.find('tbody')
            if not tbody:
                continue
            
            for row in tbody.find_all('tr'):
                # Player name
                hauptlink = row.find(class_='hauptlink')
                if hauptlink:
                    player_a = hauptlink.find('a')
                    player_name = player_a.get_text(strip=True) if player_a else hauptlink.get_text(strip=True)
                else:
                    tooltip = row.find(class_='spielprofil_tooltip')
                    player_name = tooltip.get_text(strip=True) if tooltip else None
                
                if not player_name:
                    continue
                
                # Team name
                team_tooltip = row.find(class_='vereinprofil_tooltip')
                team_img = team_tooltip.find('img') if team_tooltip else None
                team_name = team_img.get('alt', '').strip() if team_img else ''
                if not team_name and team_tooltip:
                    team_name = team_tooltip.get_text(strip=True)
                team_name = normalize_team_name(team_name) if team_name else None
                
                # Position
                pos_elem = row.find(class_='pos-text')
                position = pos_elem.get_text(strip=True) if pos_elem else None
                
                # Parse cells for injury info
                cells = row.find_all('td')
                injury_type = None
                injury_since = None
                expected_return = None
                
                for i, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    
                    if i >= 2 and not injury_type and cell_text and len(cell_text) > 2:
                        if not cell.find('a') and not cell.find('img'):
                            injury_type = cell_text
                    
                    if cell_text and ('/' in cell_text or ',' in cell_text):
                        parsed = _parse_tm_date(cell_text)
                        if parsed:
                            if injury_since is None:
                                injury_since = parsed
                            else:
                                expected_return = parsed
                
                if not injury_since:
                    injury_since = datetime.now().strftime('%Y-%m-%d')
                
                injury = {
                    'player_name': player_name,
                    'team_name': team_name,
                    'position': position,
                    'injury_type': injury_type or 'Unknown',
                    'injury_since': injury_since,
                    'expected_return': expected_return,
                    'severity': _classify_severity(injury_type),
                    'status': 'out',
                    'league_code': league_code,
                }
                
                result.data.append(injury)
        
        if result.data:
            result.success = True
            logger.info(f"Scraped {len(result.data)} injuries for {config['name']}")
        else:
            result.errors.append("Parsed tables but found no injury rows")
    
    except Exception as e:
        result.errors.append(f"Parse error: {e}")
        logger.error(f"Error parsing injuries for {league_code}: {e}")
    
    return result


def _try_alternative_injury_parse(soup, result, league_code):
    """
    Alternative parsing when standard table structure isn't found.
    Transfermarkt frequently changes their layout.
    """
    try:
        all_rows = soup.find_all('tr')
        for row in all_rows:
            texts = [t.strip() for t in row.stripped_strings]
            full_text = ' '.join(texts)
            
            injury_keywords = ['injury', 'broken', 'torn', 'strain', 'sprain', 'surgery']
            if any(kw in full_text.lower() for kw in injury_keywords):
                links = row.find_all('a')
                link_texts = [a.get_text(strip=True) for a in links if a.get_text(strip=True)]
                if link_texts:
                    result.data.append({
                        'player_name': link_texts[0],
                        'injury_type': full_text[:100],
                        'injury_since': datetime.now().strftime('%Y-%m-%d'),
                        'status': 'out',
                        'severity': 'moderate',
                        'league_code': league_code,
                    })
        
        if result.data:
            result.success = True
            logger.info(f"Alternative parse found {len(result.data)} injuries")
    except Exception as e:
        result.errors.append(f"Alternative parse failed: {e}")


def ingest_scraped_injuries(
    conn: sqlite3.Connection,
    injuries: List[Dict]
) -> int:
    """
    Insert scraped injury data into the injury_records table.
    
    Returns:
        Number of records inserted
    """
    cursor = conn.cursor()
    count = 0
    
    for inj in injuries:
        # Get or create team
        team_id = None
        if inj.get('team_name'):
            team_id = get_or_create_team(conn, inj['team_name'])
        
        # Get or create player
        player_id = create_player_if_needed(
            conn,
            inj['player_name'],
            team_id=team_id,
            position=inj.get('position')
        )
        
        # Check for existing active injury for this player
        cursor.execute('''
            SELECT injury_id FROM injury_records
            WHERE player_id = ? AND status IN ('out', 'doubt')
            AND injury_type = ?
        ''', (player_id, inj.get('injury_type', 'Unknown')))
        
        existing = cursor.fetchone()
        if existing:
            # Update the existing record (refresh expected return date)
            cursor.execute('''
                UPDATE injury_records
                SET expected_return_date = ?, status = ?, severity = ?
                WHERE injury_id = ?
            ''', (
                inj.get('expected_return'),
                inj.get('status', 'out'),
                inj.get('severity', 'moderate'),
                existing[0]
            ))
        else:
            # Insert new injury record
            add_injury_record(
                conn,
                player_id=player_id,
                injury_date=inj.get('injury_since', datetime.now().strftime('%Y-%m-%d')),
                injury_type=inj.get('injury_type', 'Unknown'),
                expected_return_date=inj.get('expected_return'),
                status=inj.get('status', 'out'),
                severity=inj.get('severity', 'moderate'),
                team_id=team_id,
                source='transfermarkt'
            )
            count += 1
    
    conn.commit()
    return count


def scrape_transfermarkt_injuries(
    conn: sqlite3.Connection,
    leagues: Optional[List[str]] = None
) -> ScrapingResult:
    """
    Main entry point: scrape and ingest injury data for all leagues.
    
    Args:
        conn: Database connection
        leagues: List of league codes (default: all 5)
    
    Returns:
        ScrapingResult with overall stats
    """
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())
    
    overall = ScrapingResult(success=True)
    
    for i, lc in enumerate(leagues):
        if i > 0:
            logger.debug(f"Rate limiting: waiting {TM_DELAY}s")
            time.sleep(TM_DELAY)
        
        result = scrape_league_injuries(lc)
        
        if result.success and result.data:
            inserted = ingest_scraped_injuries(conn, result.data)
            overall.records_inserted += inserted
            overall.data.extend(result.data)
            logger.info(f"  → {inserted} new injury records for {lc}")
        else:
            overall.errors.extend(result.errors)
            logger.warning(f"  → Failed for {lc}: {result.errors}")
    
    if overall.errors:
        overall.success = len(overall.data) > 0
    
    logger.info(f"Injury scraping complete: {overall}")
    return overall


def ingest_injuries(conn: sqlite3.Connection, source: str = 'transfermarkt'):
    """
    Main entry point for injury data ingestion.
    
    Args:
        conn: Database connection
        source: Data source ('transfermarkt' or other)
    """
    logger.info(f"Starting injury data ingestion from {source}...")
    
    if source == 'transfermarkt':
        result = scrape_transfermarkt_injuries(conn)
        logger.info(f"Injury ingestion result: {result}")
    else:
        logger.warning(f"Unknown injury source: {source}")
    
    logger.info("Injury ingestion complete")

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    ingest_injuries(conn)
    conn.close()
