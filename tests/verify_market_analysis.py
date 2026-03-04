"""
Market Analysis Verification Script

Trains the Phase 2 model, generates match outcome probabilities,
then uses the market analysis module to:
1. Compare model probabilities vs Bet365 implied probabilities.
2. Identify historical value bets.
3. Simulate flat-stake ROI on those value bets.
"""

import sys
import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation
from src.features.elo import EloFeatures
from src.features.lagged_stats import LaggedStats
from src.analysis.market import (
    implied_probability, remove_margin, find_value_bets, 
    simulate_flat_stake_roi
)


def main():
    # ── Load & Feature Engineer ───────────────────────────────────
    print("Loading data...")
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)

    print("Calculating features...")
    df = PythagoreanExpectation().calculate(df)
    df = EloFeatures().calculate(df)
    df = LaggedStats(window=5).calculate(df)

    # ── Train/Test Split ──────────────────────────────────────────
    test_start = '2024-01-01'
    features = [
        'PythagoreanHome', 'PythagoreanAway',
        'EloDifference', 'EloProbHome',
        'HomeGoalsAvg', 'AwayGoalsAvg',
        'HomeShotsAvg', 'AwayShotsAvg',
        'HomeSoTAvg', 'AwaySoTAvg',
        'HomeCornersAvg', 'AwayCornersAvg'
    ]

    train_df = df[df['Date'] < test_start].dropna(subset=features).copy()
    test_df  = df[df['Date'] >= test_start].dropna(subset=features).copy()

    print(f"Train: {len(train_df)}  |  Test: {len(test_df)}")

    # ── Train model ───────────────────────────────────────────────
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('imputer', SimpleImputer(strategy='mean')),
        ('model', LogisticRegression(max_iter=1000))
    ])
    pipeline.fit(train_df[features], train_df['FTResult'])

    # Generate probabilities on test set
    proba = pipeline.predict_proba(test_df[features])
    classes = pipeline.classes_  # e.g. ['A', 'D', 'H']
    for i, cls in enumerate(classes):
        test_df[f'ModelProb{cls}'] = proba[:, i]

    acc = accuracy_score(test_df['FTResult'], pipeline.predict(test_df[features]))
    print(f"Model Accuracy on test set: {acc:.4f}")

    # ── Market Analysis ───────────────────────────────────────────
    # The historical odds columns are OddHome, OddDraw, OddAway (Bet365)
    # Filter test set to rows that have odds
    odds_cols_present = {'H': 'OddHome', 'D': 'OddDraw', 'A': 'OddAway'}
    odds_mask = test_df[list(odds_cols_present.values())].notna().all(axis=1)
    market_df = test_df[odds_mask].copy()
    print(f"\nMatches with Bet365 odds: {len(market_df)} / {len(test_df)}")

    # ── Bookmaker implied probabilities ───────────────────────────
    market_df['ImpliedHome'] = implied_probability(market_df['OddHome'])
    market_df['ImpliedDraw'] = implied_probability(market_df['OddDraw'])
    market_df['ImpliedAway'] = implied_probability(market_df['OddAway'])
    market_df['BookmakerMargin'] = (
        market_df['ImpliedHome'] + market_df['ImpliedDraw'] + market_df['ImpliedAway'] - 1
    )
    print(f"Avg Bookmaker Margin: {market_df['BookmakerMargin'].mean()*100:.2f}%")

    # ── Fair probabilities (margin removed) ───────────────────────
    fair_h, fair_d, fair_a = remove_margin(
        market_df['ImpliedHome'], market_df['ImpliedDraw'], market_df['ImpliedAway']
    )
    market_df['FairProbHome'] = fair_h
    market_df['FairProbDraw'] = fair_d
    market_df['FairProbAway'] = fair_a

    # ── Find value bets ───────────────────────────────────────────
    model_prob_cols = {
        'H': 'ModelProbH',
        'D': 'ModelProbD',
        'A': 'ModelProbA'
    }

    print("\n" + "="*60)
    print("VALUE BET ANALYSIS")
    print("="*60)

    for min_ev_threshold in [0.05, 0.10, 0.15]:
        value_bets = find_value_bets(
            market_df,
            model_prob_cols=model_prob_cols,
            odds_cols=odds_cols_present,
            min_ev=min_ev_threshold,
            min_model_prob=0.10
        )

        roi = simulate_flat_stake_roi(value_bets, stake=1.0)

        print(f"\n--- EV Threshold ≥ {min_ev_threshold*100:.0f}% ---")
        print(f"  Total Bets:    {roi['total_bets']}")
        if roi['total_bets'] > 0:
            print(f"  Wins:          {roi['wins']} ({roi['win_rate']:.1f}%)")
            print(f"  Avg Odds:      {roi['avg_odds']:.2f}")
            print(f"  Avg EV:        {roi['avg_ev']:.1f}%")
            print(f"  Total Profit:  {roi['total_profit']:+.2f} units")
            print(f"  ROI:           {roi['roi_pct']:+.2f}%")

    # ── League breakdown ──────────────────────────────────────────
    print("\n" + "="*60)
    print("VALUE BETS BY LEAGUE (EV ≥ 5%)")
    print("="*60)

    value_bets_5 = find_value_bets(
        market_df,
        model_prob_cols=model_prob_cols,
        odds_cols=odds_cols_present,
        min_ev=0.05,
        min_model_prob=0.10
    )

    if not value_bets_5.empty and 'Division' in value_bets_5.columns:
        league_map = {'E0': 'Premier League', 'D1': 'Bundesliga', 
                      'SP1': 'La Liga', 'I1': 'Serie A', 'F1': 'Ligue 1'}
        for div, name in league_map.items():
            league_bets = value_bets_5[value_bets_5['Division'] == div]
            if not league_bets.empty:
                roi = simulate_flat_stake_roi(league_bets)
                print(f"\n  {name}: {roi['total_bets']} bets, "
                      f"Win Rate {roi['win_rate']:.1f}%, "
                      f"ROI {roi['roi_pct']:+.1f}%")

    # ── Top 10 best value bets ────────────────────────────────────
    print("\n" + "="*60)
    print("TOP 10 HIGHEST EV BETS (Historical)")
    print("="*60)

    if not value_bets_5.empty:
        top10 = value_bets_5.head(10)
        for _, row in top10.iterrows():
            result_str = "✅" if row.get('Won', 0) == 1 else "❌"
            print(f"  {result_str} {row['HomeTeam']:20s} vs {row['AwayTeam']:20s} | "
                  f"Bet: {row['BetOn']} @ {row['Odds']:.2f} | "
                  f"Model: {row['ModelProb']*100:.1f}% | "
                  f"EV: {row['EV']*100:.1f}%")


if __name__ == "__main__":
    main()
