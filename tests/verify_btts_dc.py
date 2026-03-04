"""
Verification: BTTS and Double Chance Predictors

Trains and evaluates:
  1. Both Teams To Score (BTTS)
  2. Home Win or Draw (1X)
  3. Away Win or Draw (X2)

Uses both Logistic Regression and Gradient Boosting for comparison.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation
from src.features.elo import EloFeatures
from src.features.lagged_stats import LaggedStats

from src.models.btts import (
    derive_btts_target, BTTS_FEATURES, build_btts_pipeline, evaluate_btts
)
from src.models.double_chance import (
    derive_home_win_or_draw, derive_away_win_or_draw,
    DC_FEATURES, build_dc_pipeline, evaluate_dc
)


def load_and_engineer():
    """Load data and compute all features."""
    print("Loading data...")
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)

    print("Engineering features...")
    df = PythagoreanExpectation().calculate(df)
    df = EloFeatures().calculate(df)
    df = LaggedStats(window=5).calculate(df)
    return df


def run_btts(train_df, test_df):
    """Train and evaluate BTTS models."""
    y_train = derive_btts_target(train_df)
    y_test  = derive_btts_target(test_df)

    print(f"  BTTS base rate — Train: {y_train.mean():.3f}  Test: {y_test.mean():.3f}")

    available = [f for f in BTTS_FEATURES if f in train_df.columns]
    X_train = train_df[available]
    X_test  = test_df[available]

    results = {}
    for name, mtype in [('Logistic', 'logistic'), ('GBM', 'gbm')]:
        print(f"\n  ── {name} ──")
        pipe = build_btts_pipeline(mtype)
        pipe.fit(X_train, y_train)
        y_pred  = pipe.predict(X_test)
        y_proba = pipe.predict_proba(X_test)[:, 1]
        metrics = evaluate_btts(y_test, y_pred, y_proba)
        results[name] = {**metrics, 'pipeline': pipe}

    return results


def run_double_chance(train_df, test_df):
    """Train and evaluate Double Chance models."""
    available = [f for f in DC_FEATURES if f in train_df.columns]
    X_train = train_df[available]
    X_test  = test_df[available]

    results = {}

    for label, derive_fn in [('1X', derive_home_win_or_draw),
                              ('X2', derive_away_win_or_draw)]:
        y_train = derive_fn(train_df)
        y_test  = derive_fn(test_df)
        print(f"\n  {label} base rate — Train: {y_train.mean():.3f}  Test: {y_test.mean():.3f}")

        for name, mtype in [('Logistic', 'logistic'), ('GBM', 'gbm')]:
            print(f"\n  ── {label} / {name} ──")
            pipe = build_dc_pipeline(mtype)
            pipe.fit(X_train, y_train)
            y_pred  = pipe.predict(X_test)
            y_proba = pipe.predict_proba(X_test)[:, 1]
            metrics = evaluate_dc(y_test, y_pred, y_proba, label=label)
            results[f'{label}_{name}'] = {**metrics, 'pipeline': pipe}

    return results


def main():
    df = load_and_engineer()

    # Time-based split
    test_start = '2024-01-01'
    all_features = list(set(BTTS_FEATURES + DC_FEATURES))
    available = [f for f in all_features if f in df.columns]

    train_df = df[df['Date'] < test_start].dropna(subset=available).copy()
    test_df  = df[df['Date'] >= test_start].dropna(subset=available).copy()

    print(f"Train: {len(train_df)}  |  Test: {len(test_df)}\n")

    # ── BTTS ──────────────────────────────────────────────────────
    print("=" * 60)
    print("BOTH TEAMS TO SCORE (BTTS)")
    print("=" * 60)
    btts_results = run_btts(train_df, test_df)

    # ── Double Chance ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DOUBLE CHANCE (Win or Draw)")
    print("=" * 60)
    dc_results = run_double_chance(train_df, test_df)

    # ── Summary Table ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Model':<25} {'Accuracy':>10} {'ROC-AUC':>10} {'Brier':>10}")
    print("-" * 55)
    for key, m in {**{f'BTTS/{k}': v for k,v in btts_results.items()},
                   **{k: v for k,v in dc_results.items()}}.items():
        print(f"{key:<25} {m['accuracy']:>10.4f} {m['auc']:>10.4f} {m['brier']:>10.4f}")


if __name__ == "__main__":
    main()
