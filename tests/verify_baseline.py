import sys
import os

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data.loader import load_matches, preprocess_matches
from src.models.baseline import WinPercentageModel
from sklearn.metrics import accuracy_score, classification_report

def main():
    print("Loading data...")
    # Load data for top 5 leagues
    df = load_matches('src/data/historicaldata2000-25/Matches.csv')
    df = preprocess_matches(df)
    
    print(f"Loaded {len(df)} matches.")
    
    # Split into Train/Test (e.g., using 2024 as test set)
    # Assuming 'Date' column exists and is datetime
    test_start_date = '2024-01-01'
    
    train_df = df[df['Date'] < test_start_date]
    test_df = df[df['Date'] >= test_start_date]
    
    print(f"Training set: {len(train_df)} matches (before {test_start_date})")
    print(f"Test set: {len(test_df)} matches (from {test_start_date})")
    
    # Prepare X and y
    # Baseline only cares about y for now, but we pass X for structure
    X_train = train_df[['HomeTeam', 'AwayTeam']] 
    y_train = train_df['FTResult']
    
    X_test = test_df[['HomeTeam', 'AwayTeam']]
    y_test = test_df['FTResult']
    
    # Train Model
    print("\nTraining Baseline Model (Global Win %)...")
    model = WinPercentageModel()
    model.fit(X_train, y_train)
    
    print(f"Global Probabilities (A, D, H): {model.global_probs}")
    
    # Evaluate
    print("\nEvaluating...")
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"Baseline Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

if __name__ == "__main__":
    main()
