import sys
import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation
from src.features.elo import EloFeatures
from src.features.lagged_stats import LaggedStats

def main():
    print("Loading data...")
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)
    
    # 1. Pythagorean
    print("Calculating Pythagorean Expectation...")
    pe = PythagoreanExpectation()
    df = pe.calculate(df)
    
    # 2. Elo Features
    print("Calculating Elo Features...")
    elo = EloFeatures()
    df = elo.calculate(df)
    
    # 3. Lagged Stats
    print("Calculating Lagged Stats (Window=5)...")
    ls = LaggedStats(window=5)
    # This might take a while due to iteration
    # Since we need to iterate row by row to build history correctly
    # Let's verify how long it takes.
    # Actually, the LaggedStats implementation iterates rows once.
    # But wait, did I fix the syntax in LaggedStats?
    # Yes, it iterates via df.iterrows()
    # Let's run it.
    df = ls.calculate(df)
    
    # Check for NaNs (first 5 games will be NaN)
    print("Checking for NaNs in lagged stats...")
    lagged_cols = [c for c in df.columns if 'Avg' in c]
    print(df[lagged_cols].isna().sum())
    
    # Split
    test_start_date = '2024-01-01'
    train_df = df[df['Date'] < test_start_date].copy()
    test_df = df[df['Date'] >= test_start_date].copy()
    
    # Select Features
    features = [
        'PythagoreanHome', 'PythagoreanAway',
        'EloDifference', 'EloProbHome',
        'HomeGoalsAvg', 'AwayGoalsAvg',
        'HomeShotsAvg', 'AwayShotsAvg',
        'HomeSoTAvg', 'AwaySoTAvg',
        'HomeCornersAvg', 'AwayCornersAvg'
    ]
    
    # Drop rows with NaNs in training set (start of history)
    train_df = train_df.dropna(subset=features)
    test_df = test_df.dropna(subset=features) # Should be fine if history exists
    
    print(f"Training set: {len(train_df)}")
    print(f"Test set: {len(test_df)}")
    
    X_train = train_df[features]
    y_train = train_df['FTResult']
    
    X_test = test_df[features]
    y_test = test_df['FTResult']
    
    # Model Pipeline
    print("\nTraining Logistic Regression with All Features...")
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('imputer', SimpleImputer(strategy='mean')), # Just in case
        ('model', LogisticRegression(max_iter=1000))
    ])
    
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"Phase 2 Model Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Comparisons
    print("Baseline Accuracy: ~0.4153")
    print("Pythagorean Only: ~0.5009")
    print(f"Improvement over Phase 1: {acc - 0.5009:+.4f}")
    
    # Feature Importance (Coefficients)
    model = pipeline.named_steps['model']
    # Logistic Regression coefficients shape: (n_classes, n_features)
    # Let's inspect for 'H' class (usually index 2, but check classes_)
    classes = model.classes_
    print(f"Classes: {classes}")
    
    # For multiclass, coefficients are a matrix.
    # Let's just print basic magnitude for the first class (Away?) or average magnitude
    coeffs = np.mean(np.abs(model.coef_), axis=0)
    feat_imp = pd.Series(coeffs, index=features).sort_values(ascending=False)
    print("\nFeature Importance (Avg Abs Coeff):")
    print(feat_imp)

if __name__ == "__main__":
    main()
