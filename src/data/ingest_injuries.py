"""
Injury data ingestion module.

Sources:
- Transfermarkt (via scraping): https://www.transfermarkt.com/ injury lists
- Provides: injury type, expected return date, current status

This module fetches injury data and maintains a history of player availability.
"""

import sqlite3
from datetime import datetime
import pandas as pd
from typing import Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def ingest_transfermarkt_injuries_mock(conn: sqlite3.Connection):
    """
    Mock ingest function for Transfermarkt injury data.
    
    In production, this would:
    1. Scrape https://www.transfermarkt.com/ injury lists
    2. Parse injury info using BeautifulSoup
    3. Match player names to master_id using fuzzy matching
    4. Insert/update injury_records
    
    For now, this is a placeholder showing the expected interface.
    TODO: Implement actual Transfermarkt scraper or API integration
    """
    logger.info("Transfermarkt injury ingestion is in development")
    logger.info("TODO: Implement web scraper or API integration for injury data")
    
    # Example of how data would be ingested:
    # injuries_data = [
    #     {'player_name': 'Harry Kane', 'injury_type': 'hamstring', 'expected_return': '2025-02-20'},
    #     ...
    # ]
    # for injury in injuries_data:
    #     # Match to master_id, then call add_injury_record()
    #     pass

def ingest_injuries(conn: sqlite3.Connection, source: str = 'transfermarkt'):
    """
    Main entry point for injury data ingestion.
    
    Args:
        conn: Database connection
        source: Data source ('transfermarkt' or other)
    """
    logger.info(f"Starting injury data ingestion from {source}...")
    
    if source == 'transfermarkt':
        ingest_transfermarkt_injuries_mock(conn)
    else:
        logger.warning(f"Unknown injury source: {source}")
    
    logger.info("Injury ingestion complete")

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    ingest_injuries(conn)
    conn.close()
