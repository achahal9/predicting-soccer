import sys
import os
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.features.pythagorean import PythagoreanExpectation

def main():
    print("Loading data...")
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)
    
    # Calculate Pythagorean Features
    print("Calculating Pythagorean Expectation...")
    pe = PythagoreanExpectation(exponent=1.2)
    # This might take a moment as it iterates rows. 
    # Ideally should be optimized but fine for 40k rows.
    # Actually wait, 40k rows might be slow with iterrows.
    # But let's try.
    df = pe.calculate(df)
    
    # Check if calculation worked
    print(df[['Date', 'HomeTeam', 'AwayTeam', 'PythagoreanHome', 'PythagoreanAway']].tail())
    
    # Split
    test_start_date = '2024-01-01'
    train_df = df[df['Date'] < test_start_date]
    test_df = df[df['Date'] >= test_start_date]
    
    print(f"Training set: {len(train_df)}")
    print(f"Test set: {len(test_df)}")
    
    # Features
    features = ['PythagoreanHome', 'PythagoreanAway']
    X_train = train_df[features]
    y_train = train_df['FTResult']
    
    X_test = test_df[features]
    y_test = test_df['FTResult']
    
    # Model
    print("\nTraining Logistic Regression with Pythagorean features...")
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"Pythagorean Model Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Compare with Baseline (from previous run ~0.4153)
    print("Baseline Accuracy was ~0.4153")
    improvement = acc - 0.4153
    print(f"Improvement: {improvement:+.4f}")

if __name__ == "__main__":
    main()
