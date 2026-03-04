"""
Soccer Predictor — trained model wrapper.

Trains on Matches.csv (Top 5 leagues) using the Phase 2 feature set and exposes
a clean API for the dashboard.  Models are cached in memory across Streamlit
reruns via @st.cache_resource which calls SoccerPredictor().
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.calibration import CalibratedClassifierCV

# Local imports — works both when run from project root and via Streamlit
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation
from src.features.elo import EloFeatures
from src.features.lagged_stats import LaggedStats
from src.models.btts import derive_btts_target, BTTS_FEATURES, build_btts_pipeline
from src.models.double_chance import (
    derive_home_win_or_draw, derive_away_win_or_draw,
    DC_FEATURES, build_dc_pipeline,
)

MATCHES_CSV = os.path.join(_ROOT, "src", "data", "historicaldata2000-25", "Matches.csv")

RESULT_FEATURES = [
    "PythagoreanHome", "PythagoreanAway",
    "EloDifference", "EloProbHome",
    "HomeGoalsAvg", "AwayGoalsAvg",
    "HomeShotsAvg", "AwayShotsAvg",
    "HomeSoTAvg", "AwaySoTAvg",
    "HomeCornersAvg", "AwayCornersAvg",
]


class SoccerPredictor:
    """Train and serve predictions for upcoming fixtures."""

    LEAGUE_NAMES = {
        "E0": "Premier League",
        "D1": "Bundesliga",
        "SP1": "La Liga",
        "I1": "Serie A",
        "F1": "Ligue 1",
    }

    def __init__(self):
        self._df = None          # engineered feature dataframe
        self._result_pipe = None
        self._btts_pipe = None
        self._1x_pipe = None
        self._x2_pipe = None

    # ── Public ────────────────────────────────────────────────────────────────

    def train(self, matches_csv: str = MATCHES_CSV):
        """Load data, engineer features, train all models."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = load_matches(matches_csv)
            df = preprocess_matches(df)
            df = PythagoreanExpectation().calculate(df)
            df = EloFeatures().calculate(df)
            df = LaggedStats(window=5).calculate(df)

        self._df = df
        all_feats = list(set(RESULT_FEATURES + BTTS_FEATURES + DC_FEATURES))
        available = [f for f in all_feats if f in df.columns]
        train_df = df.dropna(subset=available).copy()

        self._result_pipe = self._train_result(train_df)
        self._btts_pipe   = self._train_btts(train_df)
        self._1x_pipe     = self._train_dc(train_df, "1X")
        self._x2_pipe     = self._train_dc(train_df, "X2")
        return self

    def predict_row(self, row: pd.Series) -> dict:
        """
        Predict all markets for a single feature row.
        Returns dict with keys: prob_H, prob_D, prob_A, btts, one_x, x_two.
        """
        cols_result = [c for c in RESULT_FEATURES if c in row.index]
        cols_btts   = [c for c in BTTS_FEATURES   if c in row.index]
        cols_dc     = [c for c in DC_FEATURES      if c in row.index]

        X_result = pd.DataFrame([row[cols_result]])
        X_btts   = pd.DataFrame([row[cols_btts]])
        X_dc     = pd.DataFrame([row[cols_dc]])

        proba_result = self._result_pipe.predict_proba(X_result)[0]
        classes = self._result_pipe.classes_
        class_map = {c: p for c, p in zip(classes, proba_result)}

        btts_prob = self._btts_pipe.predict_proba(X_btts)[0, 1]
        onex_prob = self._1x_pipe.predict_proba(X_dc)[0, 1]
        x2_prob   = self._x2_pipe.predict_proba(X_dc)[0, 1]

        return {
            "prob_H": class_map.get("H", 0.0),
            "prob_D": class_map.get("D", 0.0),
            "prob_A": class_map.get("A", 0.0),
            "btts":   btts_prob,
            "one_x":  onex_prob,
            "x_two":  x2_prob,
        }

    def build_features_for_teams(self, home: str, away: str,
                                  div: str | None = None) -> pd.Series | None:
        """
        Fetch the most recent feature row for a given home/away pair
        from the historical data (i.e., use their latest rolling stats).
        Returns None if either team is unknown.
        """
        if self._df is None:
            return None
        df = self._df
        # Get the latest row for each team (as home or away) to grab their stats
        last_home = df[(df["HomeTeam"] == home)].sort_values("Date").tail(1)
        last_away = df[(df["AwayTeam"] == away)].sort_values("Date").tail(1)

        if last_home.empty or last_away.empty:
            return None

        row = last_home.iloc[0].copy()
        # Overwrite away stats from last_away's perspective
        for feat in ["AwayGoalsAvg", "AwayShotsAvg", "AwaySoTAvg",
                     "AwayCornersAvg", "PythagoreanAway", "EloProbAway"]:
            if feat in last_away.columns:
                row[feat] = last_away.iloc[0][feat]

        return row

    def known_teams(self) -> set:
        """Return the set of all team names in the training data."""
        if self._df is None:
            return set()
        return set(self._df["HomeTeam"].unique()) | set(self._df["AwayTeam"].unique())

    def latest_elos(self) -> dict:
        """Return the most recent Elo for every team."""
        if self._df is None:
            return {}
        df = self._df.sort_values("Date")
        elos = {}
        for _, row in df.iterrows():
            elos[row["HomeTeam"]] = row["HomeElo"]
            elos[row["AwayTeam"]] = row["AwayElo"]
        return elos

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _base_pipeline():
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
        ])

    def _train_result(self, df):
        cols = [c for c in RESULT_FEATURES if c in df.columns]
        X, y = df[cols], df["FTResult"]
        base = LogisticRegression(max_iter=1000, random_state=42)
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
            ("model",   CalibratedClassifierCV(base, cv=3, method="isotonic")),
        ])
        pipe.fit(X, y)
        return pipe

    def _train_btts(self, df):
        cols = [c for c in BTTS_FEATURES if c in df.columns]
        X = df[cols]
        y = derive_btts_target(df)
        pipe = build_btts_pipeline("logistic")
        pipe.fit(X, y)
        return pipe

    def _train_dc(self, df, label):
        cols = [c for c in DC_FEATURES if c in df.columns]
        X = df[cols]
        y = derive_home_win_or_draw(df) if label == "1X" else derive_away_win_or_draw(df)
        pipe = build_dc_pipeline("logistic")
        pipe.fit(X, y)
        return pipe
