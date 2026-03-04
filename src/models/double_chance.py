"""
Double Chance (Win or Draw) Predictor

Two classifiers:
  1. Home Win or Draw  (1X)  — the home team does NOT lose
  2. Away Win or Draw  (X2)  — the away team does NOT lose

Target derivation:
    HomeWinOrDraw = 1  if FTResult in ('H', 'D')  else 0
    AwayWinOrDraw = 1  if FTResult in ('A', 'D')  else 0
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, classification_report, roc_auc_score, brier_score_loss
)


def derive_home_win_or_draw(df: pd.DataFrame) -> pd.Series:
    """1X: Home team wins or draws."""
    return df['FTResult'].isin(['H', 'D']).astype(int)


def derive_away_win_or_draw(df: pd.DataFrame) -> pd.Series:
    """X2: Away team wins or draws."""
    return df['FTResult'].isin(['A', 'D']).astype(int)


# Features for double-chance prediction
DC_FEATURES = [
    # Strength & form
    'PythagoreanHome', 'PythagoreanAway',
    'EloDifference', 'EloProbHome',
    # Scoring history
    'HomeGoalsAvg', 'AwayGoalsAvg',
    # Shot creation
    'HomeShotsAvg', 'AwayShotsAvg',
    'HomeSoTAvg', 'AwaySoTAvg',
    # Corners (proxy for possession/pressure)
    'HomeCornersAvg', 'AwayCornersAvg',
    # Form
    'Form3Home', 'Form5Home',
    'Form3Away', 'Form5Away',
]


def build_dc_pipeline(model_type: str = 'logistic') -> Pipeline:
    """
    Build a Double Chance prediction pipeline.

    Args:
        model_type: 'logistic' or 'gbm'.
    """
    if model_type == 'gbm':
        model = GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=42
        )
    else:
        model = LogisticRegression(max_iter=1000, random_state=42)

    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('model', model),
    ])


def evaluate_dc(y_true, y_pred, y_proba, label: str = '1X'):
    """Print evaluation metrics for a double-chance model."""
    acc = accuracy_score(y_true, y_pred)
    auc = roc_auc_score(y_true, y_proba)
    brier = brier_score_loss(y_true, y_proba)

    print(f"  Accuracy:    {acc:.4f}")
    print(f"  ROC-AUC:     {auc:.4f}")
    print(f"  Brier Score: {brier:.4f}")
    print()
    print(classification_report(y_true, y_pred,
                                target_names=[f'Not {label}', label],
                                zero_division=0))
    return {'accuracy': acc, 'auc': auc, 'brier': brier}
