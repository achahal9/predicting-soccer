import sys
import os
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation
from src.features.form_pythagorean import FormPythagorean

def evaluate_model(name, X_train, y_train, X_test, y_test, baseline_acc=0.4153):
    print(f"\n--- Training: {name} ---")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"Accuracy: {acc:.4f} (Vs Baseline: {acc - baseline_acc:+.4f})")
    print(classification_report(y_test, y_pred, zero_division=0))
    return acc

def main():
    print("Loading data...")
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)
    
    # Calculate Cumulative Pythagorean Features
    print("Calculating Cumulative Pythagorean Expectation...")
    pe_cum = PythagoreanExpectation(exponent=1.2)
    df = pe_cum.calculate(df)
    
    # Calculate Windowed Pythagorean Features (Form)
    print("Calculating Windowed Pythagorean Expectation (Last 5 Games)...")
    pe_form = FormPythagorean(window=5, exponent=1.2)
    df = pe_form.calculate(df)
    
    # Check if calculation worked
    print("\nSample Data (Recent Matches):")
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'PythagoreanHome', 'FormPythHome']
    print(df[cols].tail())
    
    # Split
    test_start_date = '2024-01-01'
    train_df = df[df['Date'] < test_start_date].copy()
    test_df = df[df['Date'] >= test_start_date].copy()
    
    print(f"\nTraining set: {len(train_df)}")
    print(f"Test set: {len(test_df)}")
    
    y_train = train_df['FTResult']
    y_test = test_df['FTResult']
    
    # 1. Cumulative Only (Existing Logic)
    X_train_cum = train_df[['PythagoreanHome', 'PythagoreanAway']]
    X_test_cum = test_df[['PythagoreanHome', 'PythagoreanAway']]
    acc_cum = evaluate_model("Cumulative Only", X_train_cum, y_train, X_test_cum, y_test)
    
    # 2. Form Only
    X_train_form = train_df[['FormPythHome', 'FormPythAway']]
    X_test_form = test_df[['FormPythHome', 'FormPythAway']]
    acc_form = evaluate_model("Form Only", X_train_form, y_train, X_test_form, y_test)
    
    # 3. Combined
    features = ['PythagoreanHome', 'PythagoreanAway', 'FormPythHome', 'FormPythAway']
    X_train_comb = train_df[features]
    X_test_comb = test_df[features]
    acc_comb = evaluate_model("Combined (Cumulative + Form)", X_train_comb, y_train, X_test_comb, y_test)
    
    print("\n=== Summary Comparison ===")
    print(f"Baseline (Global Win %):    0.4153")
    print(f"Cumulative Pythagorean:     {acc_cum:.4f}")
    print(f"Form Pythagorean (Last 5):  {acc_form:.4f}")
    print(f"Combined Pyth:              {acc_comb:.4f}")

if __name__ == "__main__":
    main()
