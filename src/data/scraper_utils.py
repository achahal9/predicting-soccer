"""
Shared utilities for Scrapling-based web scrapers.

Provides:
- League/team configuration mappings across data sources
- Team name normalization
- Fuzzy player matching
- Rate limiting decorator
- Standardized result types
"""

import sqlite3
import time
import functools
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ─── League Configuration ────────────────────────────────────────────────────
# Maps internal division codes to source-specific identifiers

LEAGUE_CONFIG = {
    'E0': {
        'name': 'Premier League',
        'country': 'England',
        'fbref_id': '9',
        'fbref_slug': 'Premier-League',
        'tm_id': 'GB1',
        'tm_slug': 'premier-league',
    },
    'D1': {
        'name': 'Bundesliga',
        'country': 'Germany',
        'fbref_id': '20',
        'fbref_slug': 'Bundesliga',
        'tm_id': 'L1',
        'tm_slug': 'bundesliga',
    },
    'SP1': {
        'name': 'La Liga',
        'country': 'Spain',
        'fbref_id': '12',
        'fbref_slug': 'La-Liga',
        'tm_id': 'ES1',
        'tm_slug': 'laliga',
    },
    'I1': {
        'name': 'Serie A',
        'country': 'Italy',
        'fbref_id': '11',
        'fbref_slug': 'Serie-A',
        'tm_id': 'IT1',
        'tm_slug': 'serie-a',
    },
    'F1': {
        'name': 'Ligue 1',
        'country': 'France',
        'fbref_id': '13',
        'fbref_slug': 'Ligue-1',
        'tm_id': 'FR1',
        'tm_slug': 'ligue-1',
    },
}

# ─── Team Name Normalization ─────────────────────────────────────────────────
# Maps common variants to canonical names used in the `teams` table

TEAM_NAME_ALIASES = {
    # Premier League
    'man city': 'Manchester City',
    'manchester city': 'Manchester City',
    'man utd': 'Manchester United',
    'man united': 'Manchester United',
    'manchester united': 'Manchester United',
    'manchester utd': 'Manchester United',
    'spurs': 'Tottenham',
    'tottenham hotspur': 'Tottenham',
    'tottenham': 'Tottenham',
    'wolves': 'Wolverhampton',
    'wolverhampton wanderers': 'Wolverhampton',
    'wolverhampton': 'Wolverhampton',
    'newcastle': 'Newcastle United',
    'newcastle united': 'Newcastle United',
    'newcastle utd': 'Newcastle United',
    'west ham united': 'West Ham',
    'west ham': 'West Ham',
    'nott\'m forest': 'Nottingham Forest',
    'nottingham forest': 'Nottingham Forest',
    'nott forest': 'Nottingham Forest',
    'brighton & hove albion': 'Brighton',
    'brighton and hove albion': 'Brighton',
    'brighton': 'Brighton',
    'crystal palace': 'Crystal Palace',
    'leicester': 'Leicester City',
    'leicester city': 'Leicester City',
    'ipswich': 'Ipswich Town',
    'ipswich town': 'Ipswich Town',
    'afc bournemouth': 'Bournemouth',
    'bournemouth': 'Bournemouth',
    'arsenal fc': 'Arsenal',
    'arsenal': 'Arsenal',
    'chelsea fc': 'Chelsea',
    'chelsea': 'Chelsea',
    'liverpool fc': 'Liverpool',
    'liverpool': 'Liverpool',
    'everton fc': 'Everton',
    'everton': 'Everton',
    'aston villa': 'Aston Villa',
    'fulham fc': 'Fulham',
    'fulham': 'Fulham',
    'brentford fc': 'Brentford',
    'brentford': 'Brentford',
    'southampton fc': 'Southampton',
    'southampton': 'Southampton',
    # Bundesliga
    'bayern munich': 'Bayern Munich',
    'bayern münchen': 'Bayern Munich',
    'fc bayern münchen': 'Bayern Munich',
    'bayer leverkusen': 'Bayer Leverkusen',
    'bayer 04 leverkusen': 'Bayer Leverkusen',
    'borussia dortmund': 'Borussia Dortmund',
    'dortmund': 'Borussia Dortmund',
    'rb leipzig': 'RB Leipzig',
    'rasenballsport leipzig': 'RB Leipzig',
    'eintracht frankfurt': 'Eintracht Frankfurt',
    'vfb stuttgart': 'VfB Stuttgart',
    'stuttgart': 'VfB Stuttgart',
    'sc freiburg': 'SC Freiburg',
    'freiburg': 'SC Freiburg',
    'tsg hoffenheim': 'TSG Hoffenheim',
    'hoffenheim': 'TSG Hoffenheim',
    'vfl wolfsburg': 'VfL Wolfsburg',
    'wolfsburg': 'VfL Wolfsburg',
    'union berlin': 'Union Berlin',
    '1. fc union berlin': 'Union Berlin',
    'borussia mönchengladbach': 'Borussia Mönchengladbach',
    "borussia m'gladbach": 'Borussia Mönchengladbach',
    'gladbach': 'Borussia Mönchengladbach',
    'werder bremen': 'Werder Bremen',
    'sv werder bremen': 'Werder Bremen',
    'fc augsburg': 'FC Augsburg',
    'augsburg': 'FC Augsburg',
    '1. fsv mainz 05': 'Mainz 05',
    'mainz 05': 'Mainz 05',
    'mainz': 'Mainz 05',
    '1. fc heidenheim': 'FC Heidenheim',
    'heidenheim': 'FC Heidenheim',
    'fc st. pauli': 'FC St. Pauli',
    'st. pauli': 'FC St. Pauli',
    'holstein kiel': 'Holstein Kiel',
    'kiel': 'Holstein Kiel',
    # La Liga
    'real madrid cf': 'Real Madrid',
    'real madrid': 'Real Madrid',
    'fc barcelona': 'Barcelona',
    'barcelona': 'Barcelona',
    'atletico madrid': 'Atletico Madrid',
    'atlético de madrid': 'Atletico Madrid',
    'atlético madrid': 'Atletico Madrid',
    'real sociedad': 'Real Sociedad',
    'athletic bilbao': 'Athletic Bilbao',
    'athletic club': 'Athletic Bilbao',
    'real betis': 'Real Betis',
    'real betis balompié': 'Real Betis',
    'villarreal cf': 'Villarreal',
    'villarreal': 'Villarreal',
    'sevilla fc': 'Sevilla',
    'sevilla': 'Sevilla',
    'girona fc': 'Girona',
    'girona': 'Girona',
    'rcd mallorca': 'Mallorca',
    'mallorca': 'Mallorca',
    'celta vigo': 'Celta Vigo',
    'rc celta de vigo': 'Celta Vigo',
    'getafe cf': 'Getafe',
    'getafe': 'Getafe',
    'rayo vallecano': 'Rayo Vallecano',
    'ca osasuna': 'Osasuna',
    'osasuna': 'Osasuna',
    'ud las palmas': 'Las Palmas',
    'las palmas': 'Las Palmas',
    'rcd espanyol': 'Espanyol',
    'espanyol': 'Espanyol',
    'deportivo alavés': 'Alaves',
    'alavés': 'Alaves',
    'alaves': 'Alaves',
    'real valladolid cf': 'Real Valladolid',
    'real valladolid': 'Real Valladolid',
    'cd leganés': 'Leganes',
    'leganés': 'Leganes',
    'leganes': 'Leganes',
    'valencia cf': 'Valencia',
    'valencia': 'Valencia',
    # Serie A
    'inter milan': 'Inter',
    'inter': 'Inter',
    'fc internazionale': 'Inter',
    'internazionale': 'Inter',
    'ac milan': 'AC Milan',
    'milan': 'AC Milan',
    'juventus fc': 'Juventus',
    'juventus': 'Juventus',
    'ssc napoli': 'Napoli',
    'napoli': 'Napoli',
    'as roma': 'Roma',
    'roma': 'Roma',
    'ss lazio': 'Lazio',
    'lazio': 'Lazio',
    'atalanta bc': 'Atalanta',
    'atalanta': 'Atalanta',
    'acf fiorentina': 'Fiorentina',
    'fiorentina': 'Fiorentina',
    'torino fc': 'Torino',
    'torino': 'Torino',
    'bologna fc 1909': 'Bologna',
    'bologna': 'Bologna',
    'us sassuolo': 'Sassuolo',
    'sassuolo': 'Sassuolo',
    'udinese calcio': 'Udinese',
    'udinese': 'Udinese',
    'genoa cfc': 'Genoa',
    'genoa': 'Genoa',
    'us lecce': 'Lecce',
    'lecce': 'Lecce',
    'hellas verona': 'Hellas Verona',
    'hellas verona fc': 'Hellas Verona',
    'cagliari calcio': 'Cagliari',
    'cagliari': 'Cagliari',
    'empoli fc': 'Empoli',
    'empoli': 'Empoli',
    'parma calcio 1913': 'Parma',
    'parma': 'Parma',
    'como 1907': 'Como',
    'como': 'Como',
    'venezia fc': 'Venezia',
    'venezia': 'Venezia',
    'us monza': 'Monza',
    'monza': 'Monza',
    # Ligue 1
    'psg': 'Paris Saint-Germain',
    'paris saint-germain': 'Paris Saint-Germain',
    'paris sg': 'Paris Saint-Germain',
    'paris saint-germain fc': 'Paris Saint-Germain',
    'olympique de marseille': 'Marseille',
    'marseille': 'Marseille',
    'om': 'Marseille',
    'olympique lyonnais': 'Lyon',
    'lyon': 'Lyon',
    'ol': 'Lyon',
    'as monaco': 'Monaco',
    'monaco': 'Monaco',
    'losc lille': 'Lille',
    'lille': 'Lille',
    'stade rennais fc': 'Rennes',
    'rennes': 'Rennes',
    'rc lens': 'Lens',
    'lens': 'Lens',
    'ogc nice': 'Nice',
    'nice': 'Nice',
    'rc strasbourg alsace': 'Strasbourg',
    'strasbourg': 'Strasbourg',
    'toulouse fc': 'Toulouse',
    'toulouse': 'Toulouse',
    'fc nantes': 'Nantes',
    'nantes': 'Nantes',
    'stade brestois 29': 'Brest',
    'brest': 'Brest',
    'montpellier hsc': 'Montpellier',
    'montpellier': 'Montpellier',
    'stade de reims': 'Reims',
    'reims': 'Reims',
    'le havre ac': 'Le Havre',
    'le havre': 'Le Havre',
    'angers sco': 'Angers',
    'angers': 'Angers',
    'as saint-étienne': 'Saint-Etienne',
    'saint-étienne': 'Saint-Etienne',
    'saint-etienne': 'Saint-Etienne',
    'aj auxerre': 'Auxerre',
    'auxerre': 'Auxerre',
}


def normalize_team_name(name: str) -> str:
    """
    Normalize a team name to its canonical form.
    
    Tries exact lowercase match first, then returns original if no match.
    """
    if not name:
        return name
    cleaned = name.strip()
    lookup = cleaned.lower()
    return TEAM_NAME_ALIASES.get(lookup, cleaned)


def get_or_create_team(conn: sqlite3.Connection, team_name: str) -> int:
    """
    Get team_id for a team name, creating the team entry if it doesn't exist.
    Normalizes the name before lookup.
    
    Returns:
        team_id (int)
    """
    canonical = normalize_team_name(team_name)
    cursor = conn.cursor()
    
    # Try exact match
    cursor.execute('SELECT team_id FROM teams WHERE team_name = ?', (canonical,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Try case-insensitive match
    cursor.execute('SELECT team_id FROM teams WHERE LOWER(team_name) = LOWER(?)', (canonical,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Create new team
    cursor.execute(
        'INSERT INTO teams (team_name) VALUES (?)',
        (canonical,)
    )
    conn.commit()
    logger.info(f"Created new team entry: '{canonical}' (id={cursor.lastrowid})")
    return cursor.lastrowid


def fuzzy_match_player(
    conn: sqlite3.Connection,
    player_name: str,
    team_id: Optional[int] = None
) -> Optional[int]:
    """
    Find a player's master_id using fuzzy name matching.
    
    Strategy:
    1. Exact match on full_name
    2. Case-insensitive match
    3. Partial match (last name)
    4. If team_id given, prefer players on that team's roster
    
    Returns:
        master_id or None if no match found
    """
    cursor = conn.cursor()
    
    # 1. Exact match
    cursor.execute('SELECT master_id FROM players WHERE full_name = ?', (player_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # 2. Case-insensitive match
    cursor.execute(
        'SELECT master_id FROM players WHERE LOWER(full_name) = LOWER(?)',
        (player_name,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # 3. Last name match (for names like "K. De Bruyne" → "Kevin De Bruyne")
    parts = player_name.split()
    if len(parts) >= 2:
        # Try matching on last name(s) — take everything after first token
        last_name = ' '.join(parts[1:]).strip('.')
        if len(last_name) > 2:
            cursor.execute(
                "SELECT master_id FROM players WHERE full_name LIKE ?",
                (f'%{last_name}%',)
            )
            results = cursor.fetchall()
            if len(results) == 1:
                return results[0][0]
            elif len(results) > 1 and team_id:
                # Disambiguate by team roster
                ids = [r[0] for r in results]
                placeholders = ','.join('?' * len(ids))
                cursor.execute(f'''
                    SELECT player_id FROM team_rosters
                    WHERE player_id IN ({placeholders}) AND team_id = ?
                    ORDER BY season DESC LIMIT 1
                ''', ids + [team_id])
                row = cursor.fetchone()
                if row:
                    return row[0]
    
    return None


def create_player_if_needed(
    conn: sqlite3.Connection,
    player_name: str,
    team_id: Optional[int] = None,
    position: Optional[str] = None
) -> int:
    """
    Find or create a player entry. Returns master_id.
    """
    master_id = fuzzy_match_player(conn, player_name, team_id)
    if master_id:
        return master_id
    
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO players (full_name, position) VALUES (?, ?)',
        (player_name, position)
    )
    conn.commit()
    logger.info(f"Created new player entry: '{player_name}' (id={cursor.lastrowid})")
    return cursor.lastrowid


# ─── Rate Limiting ────────────────────────────────────────────────────────────

def rate_limit(delay: float = 3.0):
    """
    Decorator that adds a delay between calls to respect rate limits.
    
    Args:
        delay: Seconds to wait between calls (default 3.0s)
    """
    def decorator(func):
        last_call_time = [0.0]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call_time[0]
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            
            result = func(*args, **kwargs)
            last_call_time[0] = time.time()
            return result
        
        return wrapper
    return decorator


# ─── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class ScrapingResult:
    """Standardized result from a scraping operation."""
    success: bool
    data: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    source_url: str = ''
    records_inserted: int = 0
    records_updated: int = 0
    
    def __str__(self):
        status = '✓' if self.success else '✗'
        return (
            f"{status} ScrapingResult: {len(self.data)} items scraped, "
            f"{self.records_inserted} inserted, {self.records_updated} updated, "
            f"{len(self.errors)} errors"
        )


def get_current_season_code() -> str:
    """
    Get current season code (e.g. '2526' for 2025-26 season).
    Based on current date.
    """
    from datetime import datetime
    now = datetime.now()
    year = now.year
    if now.month > 7:
        start = year % 100
        end = (year + 1) % 100
    else:
        start = (year - 1) % 100
        end = year % 100
    return f"{start:02d}{end:02d}"


def get_current_season_year() -> int:
    """
    Get the start year of the current season (e.g. 2025 for 2025-26).
    """
    from datetime import datetime
    now = datetime.now()
    if now.month > 7:
        return now.year
    else:
        return now.year - 1
