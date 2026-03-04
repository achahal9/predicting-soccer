"""
Market Analysis Module

Compares model probabilities against bookmaker odds to identify
value bets (positive Expected Value).

Key Concepts:
- Implied Probability: 1 / Odds (e.g., odds of 2.0 = 50% implied)
- Bookmaker Margin: Sum of implied probs > 1 (the "vig")
- Value Bet: Model probability > Fair implied probability
- Expected Value: (Model_Prob * Odds) - 1  (positive = value)
"""

import pandas as pd
import numpy as np
from typing import Optional


def implied_probability(odds: pd.Series) -> pd.Series:
    """Convert decimal odds to implied probability."""
    return 1.0 / odds


def remove_margin(prob_home: pd.Series, prob_draw: pd.Series, 
                  prob_away: pd.Series) -> tuple:
    """
    Remove bookmaker margin to get 'fair' probabilities.
    
    Uses the multiplicative method: divide each implied prob by total.
    """
    total = prob_home + prob_draw + prob_away
    return prob_home / total, prob_draw / total, prob_away / total


def calculate_expected_value(model_prob: pd.Series, odds: pd.Series) -> pd.Series:
    """
    Calculate Expected Value for a bet.
    
    EV = (probability * odds) - 1
    Positive EV = value bet.
    """
    return (model_prob * odds) - 1.0


def find_value_bets(df: pd.DataFrame, 
                    model_prob_cols: dict,
                    odds_cols: dict,
                    min_ev: float = 0.05,
                    min_model_prob: float = 0.0) -> pd.DataFrame:
    """
    Identify value bets where model probability exceeds fair bookmaker probability.
    
    Args:
        df: DataFrame with model probabilities and odds columns.
        model_prob_cols: Dict mapping outcome to model prob column name.
                        e.g. {'H': 'ModelProbHome', 'D': 'ModelProbDraw', 'A': 'ModelProbAway'}
        odds_cols: Dict mapping outcome to odds column name.
                   e.g. {'H': 'OddHome', 'D': 'OddDraw', 'A': 'OddAway'}
        min_ev: Minimum expected value threshold (default 5%).
        min_model_prob: Minimum model probability to consider (filter noise).
        
    Returns:
        DataFrame of value bets with columns:
        ['Date', 'HomeTeam', 'AwayTeam', 'BetOn', 'ModelProb', 'Odds', 'EV', 'FTResult']
    """
    value_bets = []
    
    for outcome, prob_col in model_prob_cols.items():
        odds_col = odds_cols[outcome]
        
        # Skip rows where odds or probabilities are missing
        mask = df[prob_col].notna() & df[odds_col].notna() & (df[odds_col] > 0)
        subset = df[mask].copy()
        
        if subset.empty:
            continue
        
        ev = calculate_expected_value(subset[prob_col], subset[odds_col])
        
        # Filter by EV threshold and minimum probability
        value_mask = (ev >= min_ev) & (subset[prob_col] >= min_model_prob)
        value_subset = subset[value_mask].copy()
        
        if value_subset.empty:
            continue
            
        value_subset['BetOn'] = outcome
        value_subset['ModelProb'] = value_subset[prob_col]
        value_subset['Odds'] = value_subset[odds_col]
        value_subset['EV'] = ev[value_mask]
        
        # Determine if bet won
        if 'FTResult' in value_subset.columns:
            value_subset['Won'] = (value_subset['FTResult'] == outcome).astype(int)
        
        cols_to_keep = ['Date', 'HomeTeam', 'AwayTeam', 'BetOn', 'ModelProb', 
                        'Odds', 'EV']
        if 'FTResult' in value_subset.columns:
            cols_to_keep.extend(['FTResult', 'Won'])
        if 'Division' in value_subset.columns:
            cols_to_keep.insert(0, 'Division')
            
        value_bets.append(value_subset[cols_to_keep])
    
    if not value_bets:
        return pd.DataFrame()
    
    result = pd.concat(value_bets, ignore_index=True)
    result = result.sort_values('EV', ascending=False)
    return result


def simulate_flat_stake_roi(value_bets: pd.DataFrame, stake: float = 1.0) -> dict:
    """
    Simulate ROI using flat staking on identified value bets.
    
    Args:
        value_bets: DataFrame from find_value_bets (must have 'Won' and 'Odds').
        stake: Flat stake per bet.
    
    Returns:
        Dict with ROI metrics.
    """
    if value_bets.empty or 'Won' not in value_bets.columns:
        return {'total_bets': 0, 'roi': 0.0}
    
    total_bets = len(value_bets)
    total_staked = total_bets * stake
    
    # Profit = (Odds * Stake - Stake) for wins, -Stake for losses
    value_bets = value_bets.copy()
    value_bets['Profit'] = np.where(
        value_bets['Won'] == 1,
        (value_bets['Odds'] * stake) - stake,
        -stake
    )
    
    total_profit = value_bets['Profit'].sum()
    roi = (total_profit / total_staked) * 100 if total_staked > 0 else 0
    win_rate = value_bets['Won'].mean() * 100
    avg_odds = value_bets['Odds'].mean()
    
    return {
        'total_bets': total_bets,
        'wins': int(value_bets['Won'].sum()),
        'win_rate': round(win_rate, 2),
        'avg_odds': round(avg_odds, 2),
        'avg_ev': round(value_bets['EV'].mean() * 100, 2),
        'total_staked': round(total_staked, 2),
        'total_profit': round(total_profit, 2),
        'roi_pct': round(roi, 2)
    }
