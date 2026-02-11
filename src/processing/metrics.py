"""
Soccer analytics metrics module.

Includes:
- Pythagorean expectation (luck metric)
- Expected goals (xG) analysis
- Shot efficiency metrics
- Team formation analysis
- Head-to-head historical analysis
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_pythagorean_expectation(goals_for, goals_against, exponent=1.35):
    """
    Calculates the expected winning percentage based on goals scored and conceded.
    
    The Pythagorean expectation identifies 'lucky' (overperforming) or 
    'unlucky' (underperforming) teams - a reversion metric.
    
    Args:
        goals_for: Total goals scored by team
        goals_against: Total goals conceded by team
        exponent: Power exponent (default 1.35 for soccer, varies by league)
    
    Returns:
        Expected win percentage (0-1)
    """
    if goals_for == 0 and goals_against == 0:
        return 0.5
        
    numerator = goals_for ** exponent
    denominator = (goals_for ** exponent) + (goals_against ** exponent)
    
    return numerator / denominator

def get_performance_gap(actual_win_pct, expected_win_pct) -> float:
    """
    Calculate the performance gap (luck) metric.
    
    Args:
        actual_win_pct: Actual win percentage achieved
        expected_win_pct: Pythagorean expectation
    
    Returns:
        Gap: Positive = Overperforming (lucky), Negative = Underperforming (unlucky)
    """
    return actual_win_pct - expected_win_pct

def calculate_shot_efficiency(goals, shots):
    """
    Calculate shooting efficiency (conversion rate).
    
    Args:
        goals: Goals scored
        shots: Total shots
    
    Returns:
        Goal-per-shot percentage (0-1)
    """
    if shots == 0:
        return 0.0
    return goals / shots

def calculate_expected_goals_efficiency(expected_goals, actual_goals) -> float:
    """
    Compare actual goals to expected goals (xG underperformance/overperformance).
    
    Positive = Overperforming (clinical finishing)
    Negative = Underperforming (wasteful)
    """
    if expected_goals == 0:
        return 0.0
    return actual_goals - expected_goals

def analyze_head_to_head(
    conn: sqlite3.Connection,
    team1_id: int,
    team2_id: int,
    limit: Optional[int] = None
) -> Dict:
    """
    Analyze historical head-to-head record between two teams.
    
    Args:
        conn: Database connection
        team1_id: First team ID
        team2_id: Second team ID
        limit: Maximum number of matches to analyze
    
    Returns:
        Dict with: team1_wins, team1_draws, team1_losses, avg_goals_for, avg_goals_against, etc.
    """
    query = '''
        SELECT 
            m.home_team_id, m.away_team_id,
            m.home_goals, m.away_goals,
            m.date
        FROM match_results m
        WHERE (
            (m.home_team_id = ? AND m.away_team_id = ?)
            OR 
            (m.home_team_id = ? AND m.away_team_id = ?)
        )
        ORDER BY m.date DESC
    '''
    
    params = [team1_id, team2_id, team2_id, team1_id]
    
    if limit:
        query += f' LIMIT {limit}'
    
    matches = pd.read_sql_query(query, conn, params=params)
    
    if len(matches) == 0:
        return {
            'total_matches': 0,
            'team1_wins': 0,
            'team1_draws': 0,
            'team1_losses': 0,
            'team1_goals_for': 0,
            'team1_goals_against': 0
        }
    
    team1_wins = 0
    team1_draws = 0
    team1_losses = 0
    team1_goals_for = 0
    team1_goals_against = 0
    
    for _, row in matches.iterrows():
        is_team1_home = row['home_team_id'] == team1_id
        
        goals_for = row['home_goals'] if is_team1_home else row['away_goals']
        goals_against = row['away_goals'] if is_team1_home else row['home_goals']
        
        team1_goals_for += goals_for
        team1_goals_against += goals_against
        
        if goals_for > goals_against:
            team1_wins += 1
        elif goals_for == goals_against:
            team1_draws += 1
        else:
            team1_losses += 1
    
    total = len(matches)
    return {
        'total_matches': total,
        'team1_wins': team1_wins,
        'team1_draws': team1_draws,
        'team1_losses': team1_losses,
        'team1_win_pct': round(team1_wins / total, 3) if total > 0 else 0,
        'team1_goals_for': team1_goals_for,
        'team1_goals_against': team1_goals_against,
        'team1_goal_diff': team1_goals_for - team1_goals_against,
        'avg_goals_per_match': round(team1_goals_for / total, 2) if total > 0 else 0
    }

def calculate_defensive_strength(goals_against, matches_played) -> float:
    """
    Calculate defensive rating: goals conceded per match.
    
    Lower is better.
    """
    if matches_played == 0:
        return 0.0
    return round(goals_against / matches_played, 2)

def calculate_attacking_strength(goals_for, matches_played) -> float:
    """
    Calculate attacking rating: goals scored per match.
    
    Higher is better.
    """
    if matches_played == 0:
        return 0.0
    return round(goals_for / matches_played, 2)

def analyze_team_consistency(
    conn: sqlite3.Connection,
    team_id: int,
    season: str,
    metric: str = 'goals_for'
) -> Dict:
    """
    Analyze consistency of a team's performance (variance in match outcome).
    
    Args:
        conn: Database connection
        team_id: Team ID
        season: Season (e.g., '2425')
        metric: 'goals_for', 'goals_against', or 'goal_diff'
    
    Returns:
        Dict with mean, std_dev, min, max, coefficient_of_variation
    """
    query = '''
        SELECT 
            CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END as goals_for,
            CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END as goals_against
        FROM match_results
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND season = ?
        ORDER BY date
    '''
    
    matches = pd.read_sql_query(query, conn, params=[team_id, team_id, team_id, team_id, season])
    
    if len(matches) == 0:
        return {}
    
    if metric == 'goals_for':
        values = matches['goals_for']
    elif metric == 'goals_against':
        values = matches['goals_against']
    else:  # goal_diff
        values = matches['goals_for'] - matches['goals_against']
    
    mean = values.mean()
    std = values.std()
    cv = (std / mean) if mean != 0 else 0
    
    return {
        'metric': metric,
        'mean': round(mean, 2),
        'std_dev': round(std, 2),
        'min': int(values.min()),
        'max': int(values.max()),
        'coefficient_of_variation': round(cv, 3),
        'matches': len(matches)
    }

def get_formation_analysis(
    conn: sqlite3.Connection,
    team_id: int,
    season: str
) -> pd.DataFrame:
    """
    Analyze the team's most common formations in a season.
    
    Requires match lineups to be ingested.
    Returns top 5 most-used formations and their records.
    """
    query = '''
        SELECT 
            GROUP_CONCAT(p.position, ',') as formation,
            COUNT(*) as frequency,
            AVG(CASE WHEN m.home_team_id = ? AND m.home_goals > m.away_goals THEN 1
                     WHEN m.away_team_id = ? AND m.away_goals > m.home_goals THEN 1
                     ELSE 0 END) as win_rate
        FROM match_lineups ml
        JOIN match_results m ON ml.match_id = m.match_id
        JOIN players p ON ml.player_id = p.master_id
        WHERE ml.team_id = ? AND m.season = ? AND ml.is_starter = 1
        GROUP BY formation
        ORDER BY frequency DESC
        LIMIT 5
    '''
    
    return pd.read_sql_query(query, conn, params=[team_id, team_id, team_id, season])

def calculate_home_away_split(
    conn: sqlite3.Connection,
    team_id: int,
    season: Optional[str] = None
) -> Dict:
    """
    Calculate team's home vs away performance.
    
    Returns: home_record, away_record, home_goal_diff, away_goal_diff, etc.
    """
    query = '''
        SELECT 
            CASE WHEN home_team_id = ? THEN 'home' ELSE 'away' END as location,
            COUNT(*) as matches,
            SUM(CASE WHEN (home_team_id = ? AND home_goals > away_goals)
                  OR (away_team_id = ? AND away_goals > home_goals) THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN home_team_id = ? THEN home_goals ELSE away_goals END) as goals_for,
            SUM(CASE WHEN home_team_id = ? THEN away_goals ELSE home_goals END) as goals_against
        FROM match_results
        WHERE (home_team_id = ? OR away_team_id = ?)
    '''
    params = [team_id, team_id, team_id, team_id, team_id, team_id, team_id]
    
    if season:
        query += ' AND season = ?'
        params.append(season)
    
    query += ' GROUP BY location'
    
    results = pd.read_sql_query(query, conn, params=params)
    
    home_data = results[results['location'] == 'home'].iloc[0] if len(results) > 0 else None
    away_data = results[results['location'] == 'away'].iloc[0] if len(results) > 1 else None
    
    return {
        'home_matches': int(home_data['matches']) if home_data is not None else 0,
        'home_wins': int(home_data['wins']) if home_data is not None else 0,
        'home_draws': int(home_data['draws']) if home_data is not None else 0,
        'home_gf': int(home_data['goals_for']) if home_data is not None else 0,
        'home_ga': int(home_data['goals_against']) if home_data is not None else 0,
        'away_matches': int(away_data['matches']) if away_data is not None else 0,
        'away_wins': int(away_data['wins']) if away_data is not None else 0,
        'away_draws': int(away_data['draws']) if away_data is not None else 0,
        'away_gf': int(away_data['goals_for']) if away_data is not None else 0,
        'away_ga': int(away_data['goals_against']) if away_data is not None else 0
    }

def compatibility_score(
    player_stats1: Dict,
    player_stats2: Dict,
    position: str = 'generic'
) -> float:
    """
    Calculate compatibility score between two players (e.g., for transfer analysis).
    
    Considers: age similarity, nationality, position, playing style, etc.
    
    Args:
        player_stats1: First player's attributes
        player_stats2: Second player's attributes
        position: Positional category
    
    Returns:
        Compatibility score 0-1 (higher = better fit)
    
    TODO: Implement more sophisticated compatibility logic with playing style data
    """
    # Placeholder implementation
    # In production, would incorporate tactical/style data
    score = 0.5
    
    if player_stats1.get('position') == player_stats2.get('position'):
        score += 0.2
    
    age_diff = abs(player_stats1.get('age', 0) - player_stats2.get('age', 0))
    if age_diff < 3:
        score += 0.15
    
    if player_stats1.get('nationality') and player_stats2.get('nationality'):
        if player_stats1['nationality'] == player_stats2['nationality']:
            score += 0.15
    
    return min(score, 1.0)