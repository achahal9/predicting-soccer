"""
Schedule and travel metrics module.

Computes team fatigue and scheduling difficulty metrics:
- Days since last match
- Matches played in last N days
- Consecutive away matches
- Travel distance between venues
- Overall "congestion" score

These metrics help predict team tiredness and fixture congestion impact.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Premier League stadium coordinates for travel distance calculation
PL_VENUES = {
    'Arsenal': (51.555, -0.108),
    'Aston Villa': (52.509, -1.884),
    'Bournemouth': (50.735, -1.838),
    'Brentford': (51.491, -0.294),
    'Brighton': (50.861, -0.083),
    'Chelsea': (51.482, -0.191),
    'Crystal Palace': (51.398, -0.085),
    'Everton': (53.439, -2.966),
    'Fulham': (51.475, -0.222),
    'Ipswich Town': (52.054, 1.145),
    'Leicester City': (52.620, -1.142),
    'Liverpool': (53.431, -2.961),
    'Manchester City': (53.483, -2.200),
    'Manchester United': (53.463, -2.291),
    'Newcastle United': (54.975, -1.622),
    'Nottingham Forest': (52.940, -1.133),
    'Southampton': (50.906, -1.391),
    'Tottenham': (51.604, -0.066),
    'West Ham': (51.539, 0.016),
    'Wolverhampton': (52.510, -2.130),
}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two lat/lon points using Haversine formula.
    
    Returns distance in kilometers.
    """
    from math import radians, sqrt, sin, cos, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def get_travel_distance(from_team: str, to_team: str) -> Optional[float]:
    """Get travel distance between two team venues."""
    if from_team not in PL_VENUES or to_team not in PL_VENUES:
        return None
    
    from_lat, from_lon = PL_VENUES[from_team]
    to_lat, to_lon = PL_VENUES[to_team]
    
    return haversine_distance(from_lat, from_lon, to_lat, to_lon)

def get_team_matches_before_date(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str,
    limit: int = 10
) -> pd.DataFrame:
    """
    Get matches for a team before a given date.
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Match date (YYYY-MM-DD)
        limit: Max matches to return
    
    Returns:
        DataFrame of matches in reverse chronological order
    """
    query = '''
        SELECT m.match_id, m.date, 
               CASE WHEN m.home_team_id = ? THEN 1 ELSE 0 END as is_home,
               CASE WHEN m.home_team_id = ? THEN away_team_id ELSE home_team_id END as opponent_id,
               ht.team_name as home_team, at.team_name as away_team
        FROM match_results m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.date < ?
        ORDER BY m.date DESC
        LIMIT ?
    '''
    return pd.read_sql_query(query, conn, params=[team_id, team_id, team_id, team_id, match_date, limit])

def calculate_days_rest(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str
) -> Optional[int]:
    """
    Calculate days rest since last match for a team.
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
    
    Returns:
        Number of days rest, or None if no prior matches
    """
    recent_matches = get_team_matches_before_date(conn, team_id, match_date, limit=1)
    
    if len(recent_matches) == 0:
        return None
    
    last_match_date = pd.to_datetime(recent_matches.iloc[0]['date'])
    current_date = pd.to_datetime(match_date)
    
    return (current_date - last_match_date).days

def calculate_match_density(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str,
    days: int = 14
) -> int:
    """
    Calculate number of matches played in last N days.
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
        days: Look back period (default: 14 days)
    
    Returns:
        Number of matches in the period (excluding current match)
    """
    cutoff_date = (pd.to_datetime(match_date) - timedelta(days=days)).strftime('%Y-%m-%d')
    
    query = '''
        SELECT COUNT(*) as match_count
        FROM match_results
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND date BETWEEN ? AND ?
        AND date < ?
    '''
    result = pd.read_sql_query(query, conn, params=[team_id, team_id, cutoff_date, match_date, match_date])
    
    return result.iloc[0]['match_count']

def calculate_consecutive_away_matches(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str
) -> int:
    """
    Calculate consecutive away matches before a given date.
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
    
    Returns:
        Number of consecutive away matches
    """
    recent_matches = get_team_matches_before_date(conn, team_id, match_date, limit=10)
    
    consecutive_away = 0
    for _, match in recent_matches.iterrows():
        if match['is_home'] == 0:  # Away match
            consecutive_away += 1
        else:
            break  # Stop counting at first home match
    
    return consecutive_away

def calculate_fatigue_score(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str
) -> float:
    """
    Calculate a composite fatigue score (0-1) based on schedule.
    
    Factors:
    - Days rest (fewer = more fatigued)
    - Match density (more matches = more fatigued)
    - Consecutive away matches (more = more fatigued)
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
    
    Returns:
        Fatigue score 0-1 (0=fresh, 1=exhausted)
    """
    days_rest = calculate_days_rest(conn, team_id, match_date)
    match_density = calculate_match_density(conn, team_id, match_date, days=14)
    consecutive_away = calculate_consecutive_away_matches(conn, team_id, match_date)
    
    # Normalize components
    rest_component = max(0, 1 - (days_rest or 7) / 7) if days_rest else 0.2  # 7+ days = fresh
    density_component = min(match_density / 5, 1.0)  # 5+ matches in 2 weeks = fatigued
    away_component = min(consecutive_away / 3, 1.0)  # 3+ consecutive away = fatigued
    
    # Weighted average
    fatigue = (rest_component * 0.5 + density_component * 0.3 + away_component * 0.2)
    
    return round(fatigue, 2)

def build_schedule_metrics_table(conn: sqlite3.Connection):
    """
    Create a view/derived table with schedule metrics for all upcoming matches.
    
    This helps with feature engineering later.
    """
    logger.info("Building schedule metrics...")
    
    cursor = conn.cursor()
    
    # Get all matches in chronological order
    matches = pd.read_sql_query('''
        SELECT match_id, date, home_team_id, away_team_id
        FROM match_results
        ORDER BY date
    ''', conn)
    
    metrics_data = []
    
    for _, row in matches.iterrows():
        match_id = row['match_id']
        match_date = row['date']
        home_team_id = row['home_team_id']
        away_team_id = row['away_team_id']
        
        # Home team metrics
        home_rest = calculate_days_rest(conn, home_team_id, match_date)
        home_density = calculate_match_density(conn, home_team_id, match_date)
        home_fatigue = calculate_fatigue_score(conn, home_team_id, match_date)
        
        # Away team metrics
        away_rest = calculate_days_rest(conn, away_team_id, match_date)
        away_density = calculate_match_density(conn, away_team_id, match_date)
        away_fatigue = calculate_fatigue_score(conn, away_team_id, match_date)
        
        # Travel distance (for away team)
        away_team_name = pd.read_sql_query(
            'SELECT team_name FROM teams WHERE team_id = ?',
            conn, params=[away_team_id]
        ).iloc[0]['team_name']
        home_team_name = pd.read_sql_query(
            'SELECT team_name FROM teams WHERE team_id = ?',
            conn, params=[home_team_id]
        ).iloc[0]['team_name']
        
        travel_distance = get_travel_distance(away_team_name, home_team_name)
        
        metrics_data.append({
            'match_id': match_id,
            'home_days_rest': home_rest,
            'home_match_density_14d': home_density,
            'home_fatigue_score': home_fatigue,
            'away_days_rest': away_rest,
            'away_match_density_14d': away_density,
            'away_fatigue_score': away_fatigue,
            'away_travel_distance_km': travel_distance
        })
    
    # Store in a temporary table or as a view
    metrics_df = pd.DataFrame(metrics_data)
    metrics_df.to_sql('schedule_metrics', conn, if_exists='replace', index=False)
    logger.info(f"Schedule metrics computed for {len(metrics_df)} matches")

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    build_schedule_metrics_table(conn)
    conn.close()
