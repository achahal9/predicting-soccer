"""
Transfer activity scraper.

Scrapes current-season transfers from Transfermarkt using Playwright
for Cloudflare bypass + BeautifulSoup for parsing.

Usage:
    python -m src.data.scrape_transfers              # All leagues
    python -m src.data.scrape_transfers --league E0  # PL only
"""

import sqlite3
import time
import re
import logging
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
from datetime import datetime

from src.data.scraper_utils import (
    LEAGUE_CONFIG,
    normalize_team_name,
    get_or_create_team,
    create_player_if_needed,
    get_current_season_year,
    ScrapingResult,
)

logger = logging.getLogger(__name__)

TM_DELAY = 5.0


def _fetch_tm_page(url: str) -> Optional[BeautifulSoup]:
    """
    Fetch a Transfermarkt page using Playwright (Cloudflare bypass).
    Falls back to requests if Playwright is unavailable.
    """
    # Try Playwright first (stealth browser)
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
            # Wait for content to load
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
        
        return BeautifulSoup(html, 'html.parser')
    except ImportError:
        logger.warning("Playwright not installed, falling back to requests")
    except Exception as e:
        logger.warning(f"Playwright failed ({e}), falling back to requests")
    
    # Fallback: requests (may be blocked by Cloudflare)
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


def scrape_league_transfers(
    league_code: str,
    season_year: Optional[int] = None,
) -> ScrapingResult:
    """
    Scrape transfer activity for a league from Transfermarkt.
    """
    config = LEAGUE_CONFIG.get(league_code)
    if not config:
        return ScrapingResult(success=False, errors=[f"Unknown league: {league_code}"])
    
    if season_year is None:
        season_year = get_current_season_year()
    
    tm_id = config['tm_id']
    tm_slug = config['tm_slug']
    url = (
        f"https://www.transfermarkt.com/{tm_slug}/transfers/"
        f"wettbewerb/{tm_id}/saison_id/{season_year}"
    )
    
    result = ScrapingResult(source_url=url)
    soup = _fetch_tm_page(url)
    
    if soup is None:
        result.errors.append("Failed to fetch Transfermarkt page")
        return result
    
    try:
        # Transfermarkt groups transfers by team in boxes
        team_boxes = soup.find_all('div', class_='box')
        
        current_team = None
        
        for box in team_boxes:
            # Team name from header
            header = (
                box.find(class_='table-header') or
                box.find('h2') or
                box.find(class_='content-box-headline')
            )
            if header:
                header_text = header.get_text(strip=True)
                if header_text and len(header_text) > 1:
                    current_team = normalize_team_name(header_text)
            
            # Transfer tables
            tables = box.find_all('table', class_='items')
            
            for table in tables:
                tbody = table.find('tbody')
                if not tbody:
                    continue
                
                for row in tbody.find_all('tr'):
                    # Player name
                    player_link = row.find(class_='hauptlink')
                    if player_link:
                        player_a = player_link.find('a')
                        player_name = player_a.get_text(strip=True) if player_a else player_link.get_text(strip=True)
                    else:
                        tooltip = row.find(class_='spielprofil_tooltip')
                        player_name = tooltip.get_text(strip=True) if tooltip else None
                    
                    if not player_name:
                        continue
                    
                    # Position
                    pos_elem = row.find(class_='pos-text')
                    position = pos_elem.get_text(strip=True) if pos_elem else None
                    
                    # Club images for from/to
                    club_imgs = row.find_all('img', class_='tiny_wappen')
                    club_names = [img.get('alt', '').strip() for img in club_imgs if img.get('alt')]
                    
                    # Also try tooltip clubs
                    if not club_names:
                        club_tooltips = row.find_all(class_='vereinprofil_tooltip')
                        club_names = [t.get_text(strip=True) for t in club_tooltips if t.get_text(strip=True)]
                    
                    # Transfer fee
                    fee_cell = row.find('td', class_='rechts')
                    fee_text = fee_cell.get_text(strip=True) if fee_cell else ''
                    fee_millions = _parse_fee(fee_text)
                    
                    # Transfer type
                    transfer_type = 'permanent'
                    fee_lower = fee_text.lower()
                    if 'loan' in fee_lower:
                        transfer_type = 'loan'
                    elif 'free' in fee_lower or fee_lower == '-':
                        transfer_type = 'free'
                    
                    transfer = {
                        'player_name': player_name,
                        'position': position,
                        'from_club': normalize_team_name(club_names[0]) if len(club_names) > 0 else None,
                        'to_club': normalize_team_name(club_names[1]) if len(club_names) > 1 else current_team,
                        'fee_millions': fee_millions,
                        'transfer_type': transfer_type,
                        'fee_raw': fee_text,
                        'season_year': season_year,
                        'league_code': league_code,
                    }
                    
                    result.data.append(transfer)
        
        if result.data:
            result.success = True
            logger.info(f"Scraped {len(result.data)} transfers for {config['name']}")
        else:
            # Alternative: look for any player profile links
            _try_alternative_parse(soup, result, league_code, season_year)
    
    except Exception as e:
        result.errors.append(f"Parse error: {e}")
        logger.error(f"Error parsing transfers for {league_code}: {e}")
    
    return result


def _try_alternative_parse(soup, result, league_code, season_year):
    """Alternative parsing when standard structure isn't found."""
    try:
        links = soup.find_all('a', class_='spielprofil_tooltip')
        if links:
            for link in links:
                name = link.get_text(strip=True)
                if name:
                    result.data.append({
                        'player_name': name,
                        'league_code': league_code,
                        'season_year': season_year,
                    })
            if result.data:
                result.success = True
                logger.info(f"Alternative parse found {len(result.data)} transfers")
        else:
            result.errors.append("No transfer data found")
    except Exception as e:
        result.errors.append(f"Alternative parse error: {e}")


def ingest_transfers(
    conn: sqlite3.Connection,
    league_code: str,
    transfers: List[Dict]
) -> int:
    """Insert scraped transfers into the transfers table."""
    cursor = conn.cursor()
    count = 0
    
    for t in transfers:
        sy = t.get('season_year', get_current_season_year())
        season_code = f"{sy % 100:02d}{(sy + 1) % 100:02d}"
        
        player_id = create_player_if_needed(
            conn, t['player_name'], position=t.get('position')
        )
        
        from_team_id = get_or_create_team(conn, t['from_club']) if t.get('from_club') else None
        to_team_id = get_or_create_team(conn, t['to_club']) if t.get('to_club') else None
        
        # Check for duplicate
        cursor.execute('''
            SELECT transfer_id FROM transfers
            WHERE player_id = ? AND season = ?
            AND (from_team_id = ? OR from_team_id IS NULL)
            AND (to_team_id = ? OR to_team_id IS NULL)
        ''', (player_id, season_code, from_team_id, to_team_id))
        
        if cursor.fetchone():
            continue
        
        try:
            cursor.execute('''
                INSERT INTO transfers
                (player_id, from_team_id, to_team_id, transfer_date,
                 transfer_type, transfer_fee_millions, season)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id, from_team_id, to_team_id,
                datetime.now().strftime('%Y-%m-%d'),
                t.get('transfer_type', 'permanent'),
                t.get('fee_millions'),
                season_code,
            ))
            count += 1
        except Exception as e:
            logger.debug(f"Skipping transfer for {t['player_name']}: {e}")
    
    conn.commit()
    return count


def scrape_all_transfers(
    conn: sqlite3.Connection,
    leagues: Optional[List[str]] = None,
    season_year: Optional[int] = None
) -> ScrapingResult:
    """Scrape and save transfers for all specified leagues."""
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())
    
    overall = ScrapingResult(success=True)
    
    for i, lc in enumerate(leagues):
        if i > 0:
            time.sleep(TM_DELAY)
        
        result = scrape_league_transfers(lc, season_year)
        
        if result.success and result.data:
            inserted = ingest_transfers(conn, lc, result.data)
            overall.records_inserted += inserted
            overall.data.extend(result.data)
            logger.info(f"  → {inserted} transfers inserted for {lc}")
        else:
            overall.errors.extend(result.errors)
            logger.warning(f"  → Failed for {lc}: {result.errors}")
    
    if overall.errors:
        overall.success = len(overall.data) > 0
    
    logger.info(f"Transfer scraping complete: {overall}")
    return overall


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_fee(fee_text: str) -> Optional[float]:
    """Parse transfer fee text into millions."""
    if not fee_text:
        return None
    
    fee_lower = fee_text.lower().strip()
    
    if fee_lower in ('-', '?', 'n/a', ''):
        return None
    if 'free' in fee_lower:
        return 0.0
    if 'loan' in fee_lower:
        return None
    
    match = re.search(r'([\d,.]+)\s*m', fee_lower)
    if match:
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            pass
    
    match = re.search(r'([\d,.]+)\s*(th|k)', fee_lower)
    if match:
        try:
            return float(match.group(1).replace(',', '.')) / 1000.0
        except ValueError:
            pass
    
    return None


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description='Scrape transfers from Transfermarkt')
    parser.add_argument('--league', type=str, help='Single league code (e.g. E0)')
    parser.add_argument('--season', type=int, help='Season start year (e.g. 2025)')
    parser.add_argument('--dry-run', action='store_true', help='Print results without writing to DB')
    args = parser.parse_args()
    
    leagues = [args.league] if args.league else None
    
    if args.dry_run:
        for lc in (leagues or list(LEAGUE_CONFIG.keys())):
            result = scrape_league_transfers(lc, args.season)
            name = LEAGUE_CONFIG[lc]['name']
            print(f"\n{name} Transfers ({len(result.data)} total):")
            for t in result.data[:20]:
                fee = f"€{t['fee_millions']:.1f}m" if t.get('fee_millions') else t.get('fee_raw', '?')
                print(f"  {t['player_name']}: {t.get('from_club', '?')} → {t.get('to_club', '?')} ({fee})")
            if len(result.data) > 20:
                print(f"  ... and {len(result.data) - 20} more")
            if result.errors:
                print(f"  Errors: {result.errors}")
            if lc != (leagues or list(LEAGUE_CONFIG.keys()))[-1]:
                time.sleep(TM_DELAY)
    else:
        conn = sqlite3.connect('sports_data.db')
        result = scrape_all_transfers(conn, leagues, args.season)
        print(result)
        conn.close()
