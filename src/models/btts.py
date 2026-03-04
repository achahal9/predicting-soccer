"""
Both Teams To Score (BTTS) Predictor

Binary classifier: Will both teams score at least one goal?

Target derivation:
    BTTS = 1  if FTHome >= 1 AND FTAway >= 1
    BTTS = 0  otherwise
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


def derive_btts_target(df: pd.DataFrame) -> pd.Series:
    """Derive BTTS target from full-time goals."""
    return ((df['FTHome'] >= 1) & (df['FTAway'] >= 1)).astype(int)


# Features specifically useful for BTTS prediction
BTTS_FEATURES = [
    # Strength & form
    'PythagoreanHome', 'PythagoreanAway',
    'EloDifference', 'EloProbHome',
    # Scoring history (rolling averages)
    'HomeGoalsAvg', 'AwayGoalsAvg',
    # Shot creation
    'HomeShotsAvg', 'AwayShotsAvg',
    'HomeSoTAvg', 'AwaySoTAvg',
    # Form
    'Form3Home', 'Form5Home',
    'Form3Away', 'Form5Away',
]


def build_btts_pipeline(model_type: str = 'logistic') -> Pipeline:
    """
    Build a BTTS prediction pipeline.

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


def evaluate_btts(y_true, y_pred, y_proba):
    """Print evaluation metrics for BTTS model."""
    acc = accuracy_score(y_true, y_pred)
    auc = roc_auc_score(y_true, y_proba)
    brier = brier_score_loss(y_true, y_proba)

    print(f"  Accuracy:    {acc:.4f}")
    print(f"  ROC-AUC:     {auc:.4f}")
    print(f"  Brier Score: {brier:.4f}")
    print()
    print(classification_report(y_true, y_pred, 
                                target_names=['No BTTS', 'BTTS'],
                                zero_division=0))
    return {'accuracy': acc, 'auc': auc, 'brier': brier}
