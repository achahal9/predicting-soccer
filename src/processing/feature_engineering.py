"""
Feature engineering module.

Builds match-level features for training prediction models:
- Team performance metrics (form, xG, defense)
- Schedule metrics (rest, fatigue, travel)
- Weather conditions
- Injury impact scores
- Player quality aggregates
- Historical head-to-head stats

OUTPUT: Feature matrix suitable for classification/regression models
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_team_recent_form(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str,
    lookback_matches: int = 5
) -> Dict:
    """
    Calculate team form (recent performance).
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
        lookback_matches: Number of recent matches to analyze
    
    Returns:
        Dict with: wins, draws, losses, goals_for, goals_against, xg, xga, avg_rating
    """
    query = '''
        SELECT 
            m.home_team_id, m.away_team_id,
            m.home_goals, m.away_goals,
            ts.expected_goals, ts.expected_goals_against,
            CASE 
                WHEN m.home_team_id = ? AND m.home_goals > m.away_goals THEN 1
                WHEN m.away_team_id = ? AND m.away_goals > m.home_goals THEN 1
                ELSE 0
            END as won,
            CASE 
                WHEN m.home_goals = m.away_goals THEN 1
                ELSE 0
            END as drew,
            CASE 
                WHEN m.home_team_id = ? AND m.home_goals < m.away_goals THEN 1
                WHEN m.away_team_id = ? AND m.away_goals < m.home_goals THEN 1
                ELSE 0
            END as lost
        FROM match_results m
        LEFT JOIN team_stats ts ON m.match_id = (
            SELECT match_id FROM match_results WHERE home_team_id = ? LIMIT 1
        )
        WHERE (m.home_team_id = ? OR m.away_team_id = ?)
        AND m.date < ?
        ORDER BY m.date DESC
        LIMIT ?
    '''
    
    recent = pd.read_sql_query(query, conn, params=[
        team_id, team_id, team_id, team_id, team_id, team_id, team_id, match_date, lookback_matches
    ])
    
    if len(recent) == 0:
        return {
            'wins': 0, 'draws': 0, 'losses': 0,
            'goals_for': 0, 'goals_against': 0,
            'expected_goals': 0.0, 'expected_goals_against': 0.0,
            'win_pct': 0.0, 'points_per_game': 0.0
        }
    
    wins = recent['won'].sum()
    draws = recent['drew'].sum()
    losses = recent['lost'].sum()
    
    # Goals
    goals_for = recent.apply(
        lambda x: x['home_goals'] if x['home_team_id'] == team_id else x['away_goals'],
        axis=1
    ).sum()
    goals_against = recent.apply(
        lambda x: x['away_goals'] if x['home_team_id'] == team_id else x['home_goals'],
        axis=1
    ).sum()
    
    points = wins * 3 + draws
    
    return {
        'wins': wins,
        'draws': draws,
        'losses': losses,
        'goals_for': float(goals_for),
        'goals_against': float(goals_against),
        'expected_goals': float(recent['expected_goals'].sum() or 0),
        'expected_goals_against': float(recent['expected_goals_against'].sum() or 0),
        'win_pct': round(wins / len(recent), 2) if len(recent) > 0 else 0.0,
        'points_per_game': round(points / len(recent), 2) if len(recent) > 0 else 0.0,
        'goal_diff': float(goals_for - goals_against)
    }

def get_team_aggregated_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season: str
) -> Dict:
    """Get season-to-date aggregated team stats."""
    query = '''
        SELECT * FROM team_stats
        WHERE team_id = ? AND season = ?
    '''
    
    stats = pd.read_sql_query(query, conn, params=[team_id, season])
    
    if len(stats) == 0:
        return {}
    
    row = stats.iloc[0]
    return {
        'wins_season': row['wins'],
        'draws_season': row['draws'],
        'losses_season': row['losses'],
        'gf_season': row['goals_for'],
        'ga_season': row['goals_against'],
        'xg_season': row['expected_goals'],
        'xga_season': row['expected_goals_against'],
        'possession_avg': row['possession_percent'],
        'pass_completion_avg': row['pass_completion']
    }

def get_injury_impact(
    conn: sqlite3.Connection,
    team_id: int,
    match_date: str
) -> Dict:
    """Calculate injury impact score for a team."""
    query = '''
        SELECT 
            COUNT(*) as injured_count,
            SUM(CASE WHEN status = 'out' THEN 1 ELSE 0 END) as out_count,
            SUM(CASE WHEN status = 'doubt' THEN 1 ELSE 0 END) as doubt_count
        FROM injury_records
        WHERE team_id = ?
        AND injury_date <= ?
        AND (actual_return_date IS NULL OR actual_return_date > ?)
    '''
    
    result = pd.read_sql_query(query, conn, params=[team_id, match_date, match_date])
    
    if len(result) == 0 or result.iloc[0]['injured_count'] is None:
        return {'injury_count': 0, 'injury_impact_score': 0.0}
    
    injured = result.iloc[0]['injured_count'] or 0
    impact = min(injured / 11.0, 1.0)  # Normalized by squad size
    
    return {
        'injury_count': int(injured),
        'injury_impact_score': round(impact, 2)
    }

def get_weather_for_match(conn: sqlite3.Connection, match_id: str) -> Dict:
    """Get weather conditions for a match."""
    query = '''
        SELECT * FROM match_env WHERE match_id = ?
    '''
    
    weather = pd.read_sql_query(query, conn, params=[match_id])
    
    if len(weather) == 0:
        return {
            'temp_celsius': None,
            'precipitation_mm': None,
            'wind_speed_kmh': None,
            'humidity_percent': None
        }
    
    row = weather.iloc[0]
    return {
        'temp_celsius': row['temp_celsius'],
        'precipitation_mm': row['precipitation_mm'],
        'wind_speed_kmh': row['wind_speed_kmh'],
        'humidity_percent': row['humidity_percent']
    }

def get_schedule_metrics(
    conn: sqlite3.Connection,
    match_id: str
) -> Dict:
    """Get pre-computed schedule metrics for a match."""
    query = '''
        SELECT * FROM schedule_metrics WHERE match_id = ?
    '''
    
    metrics = pd.read_sql_query(query, conn, params=[match_id])
    
    if len(metrics) == 0:
        return {
            'home_days_rest': None,
            'home_fatigue_score': None,
            'away_days_rest': None,
            'away_fatigue_score': None,
            'away_travel_km': None
        }
    
    row = metrics.iloc[0]
    return {
        'home_days_rest': row['home_days_rest'],
        'home_match_density': row['home_match_density_14d'],
        'home_fatigue_score': row['home_fatigue_score'],
        'away_days_rest': row['away_days_rest'],
        'away_match_density': row['away_match_density_14d'],
        'away_fatigue_score': row['away_fatigue_score'],
        'away_travel_km': row['away_travel_distance_km']
    }

def get_squad_quality(
    conn: sqlite3.Connection,
    team_id: int,
    match_id: str,
    match_date: str
) -> Dict:
    """Get average player quality metrics for a team."""
    # Check if we have lineup data (more accurate)
    lineup_query = '''
        SELECT COUNT(*) as lineup_count
        FROM match_lineups
        WHERE match_id = ? AND team_id = ? AND is_starter = 1
    '''
    
    has_lineup = pd.read_sql_query(lineup_query, conn, params=[match_id, team_id])
    
    if has_lineup.iloc[0]['lineup_count'] > 0:
        # Use lineup if available
        player_query = '''
            SELECT AVG(p.apps) as avg_apps, AVG(ml.rating) as avg_rating,
                   COUNT(*) as player_count
            FROM match_lineups ml
            JOIN players p ON ml.player_id = p.master_id
            WHERE ml.match_id = ? AND ml.team_id = ? AND ml.is_starter = 1
        '''
        
        stats = pd.read_sql_query(player_query, conn, params=[match_id, team_id])
        if len(stats) > 0 and stats.iloc[0]['player_count'] > 0:
            return {
                'squad_avg_rating': float(stats.iloc[0]['avg_rating'] or 0.0),
                'squad_avg_apps': float(stats.iloc[0]['avg_apps'] or 0.0)
            }
    
    # Fallback: use season player stats
    player_query = '''
        SELECT AVG(apps) as avg_apps, AVG(rating_avg) as avg_rating,
               COUNT(*) as player_count
        FROM player_stats
        WHERE team_id = ?
        AND season = substr(?, 1, 4)
        AND starts > 0
        LIMIT 11
    '''
    
    stats = pd.read_sql_query(player_query, conn, params=[team_id, match_date])
    
    if len(stats) == 0 or stats.iloc[0]['player_count'] == 0:
        return {'squad_avg_rating': 0.0, 'squad_avg_apps': 0.0}
    
    row = stats.iloc[0]
    return {
        'squad_avg_rating': float(row['avg_rating'] or 0.0),
        'squad_avg_apps': float(row['avg_apps'] or 0.0)
    }

def build_match_features(
    conn: sqlite3.Connection,
    match_id: str
) -> Optional[Dict]:
    """
    Build complete feature vector for a single match.
    
    Returns dict of features suitable for ML model input.
    """
    query = '''
        SELECT m.*, ht.team_name as home_team, at.team_name as away_team
        FROM match_results m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.match_id = ?
    '''
    
    match = pd.read_sql_query(query, conn, params=[match_id])
    
    if len(match) == 0:
        logger.warning(f"Match {match_id} not found")
        return None
    
    m = match.iloc[0]
    match_date = m['date']
    season = m['season']
    
    # Build features
    features = {
        'match_id': match_id,
        'date': match_date,
        'season': season
    }
    
    # Home team features
    home_form = get_team_recent_form(conn, int(m['home_team_id']), match_date)
    features.update({f'home_{k}': v for k, v in home_form.items()})
    
    home_season_stats = get_team_aggregated_stats(conn, int(m['home_team_id']), season)
    features.update({f'home_{k}': v for k, v in home_season_stats.items()})
    
    home_injury = get_injury_impact(conn, int(m['home_team_id']), match_date)
    features.update({f'home_{k}': v for k, v in home_injury.items()})
    
    home_quality = get_squad_quality(conn, int(m['home_team_id']), match_id, match_date)
    features.update({f'home_{k}': v for k, v in home_quality.items()})
    
    # Away team features
    away_form = get_team_recent_form(conn, int(m['away_team_id']), match_date)
    features.update({f'away_{k}': v for k, v in away_form.items()})
    
    away_season_stats = get_team_aggregated_stats(conn, int(m['away_team_id']), season)
    features.update({f'away_{k}': v for k, v in away_season_stats.items()})
    
    away_injury = get_injury_impact(conn, int(m['away_team_id']), match_date)
    features.update({f'away_{k}': v for k, v in away_injury.items()})
    
    away_quality = get_squad_quality(conn, int(m['away_team_id']), match_id, match_date)
    features.update({f'away_{k}': v for k, v in away_quality.items()})
    
    # Schedule and weather
    schedule = get_schedule_metrics(conn, match_id)
    features.update(schedule)
    
    weather = get_weather_for_match(conn, match_id)
    features.update(weather)
    
    # Target variable (if match is complete)
    if m['home_goals'] is not None and m['away_goals'] is not None:
        if m['home_goals'] > m['away_goals']:
            features['outcome'] = 'home_win'
        elif m['away_goals'] > m['home_goals']:
            features['outcome'] = 'away_win'
        else:
            features['outcome'] = 'draw'
    
    return features

def build_training_dataset(
    conn: sqlite3.Connection,
    season_filter: Optional[str] = None,
    include_incomplete: bool = False
) -> pd.DataFrame:
    """
    Build complete training dataset.
    
    Args:
        conn: Database connection
        season_filter: Optional season to filter (e.g., '2425')
        include_incomplete: Include matches without final scores
    
    Returns:
        DataFrame with all features and target
    """
    logger.info("Building training dataset...")
    
    query = 'SELECT match_id FROM match_results WHERE 1=1'
    params = []
    
    if season_filter:
        query += ' AND season = ?'
        params.append(season_filter)
    
    if not include_incomplete:
        query += ' AND home_goals IS NOT NULL AND away_goals IS NOT NULL'
    
    query += ' ORDER BY date'
    
    matches = pd.read_sql_query(query, conn, params=params)
    
    logger.info(f"Building features for {len(matches)} matches...")
    
    all_features = []
    for idx, row in matches.iterrows():
        features = build_match_features(conn, row['match_id'])
        if features:
            all_features.append(features)
        
        if (idx + 1) % 50 == 0:
            logger.info(f"  Processed {idx + 1}/{len(matches)} matches...")
    
    df = pd.DataFrame(all_features)
    logger.info(f"✓ Built features for {len(df)} matches")
    
    return df

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    dataset = build_training_dataset(conn)
    dataset.to_csv('training_features.csv', index=False)
    logger.info(f"Training dataset saved to training_features.csv")
    conn.close()
