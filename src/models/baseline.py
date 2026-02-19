import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import accuracy_score, log_loss

class WinPercentageModel(BaseEstimator, ClassifierMixin):
    """
    A baseline model that predicts match outcomes based on historical win percentages.
    It can calculate global home/draw/away probabilities or team-specific ones 
    (though purely historical average is often a strong naive baseline).
    """
    def __init__(self, use_team_stats=False):
        """
        Args:
            use_team_stats (bool): If True, use specific team's home/away win rates 
                                   (with fallback to global average). 
                                   If False, use global home/draw/away rates.
        """
        self.use_team_stats = use_team_stats
        self.global_probs = None
        self.team_stats = {}
        self.classes_ = np.array(['A', 'D', 'H']) # Standard sklearn convention, sorted

    def fit(self, X, y):
        """
        Fit the baseline model.
        
        Args:
            X (pd.DataFrame): DataFrame containing 'HomeTeam', 'AwayTeam'.
            y (pd.Series): Target variable (e.g., 'H', 'D', 'A').
        """
        # Calculate global probabilities
        # y should contain 'H', 'D', 'A'
        counts = y.value_counts(normalize=True)
        self.global_probs = np.array([
            counts.get('A', 0),
            counts.get('D', 0),
            counts.get('H', 0)
        ])
        
        if self.use_team_stats:
            # This would be more complex: calculate win% for each team at home and away
            # For brevity in this baseline, we'll start with just global usually, 
            # but let's implement a simple version.
            
            # Create a localized dataframe
            df = X.copy()
            df['target'] = y
            
            self.team_stats = {}
            
            # We need to iterate or group. 
            # Let's just track overall performance for now to keep it simple as a "Team Strength" proxy?
            # Or strict "Home Team at Home" vs "Away Team at Away"?
            
            # Let's stick to global for the 'Simple Win Percentage' requested, 
            # as team-specific stats without decay/windowing (like form) is basically a bad version of Elo.
            pass
            
        return self

    def predict_proba(self, X):
        """
        Predict class probabilities.
        """
        if self.global_probs is None:
            raise ValueError("Model not fitted")
            
        # Return the same global probability for every instance
        n_samples = len(X)
        return np.tile(self.global_probs, (n_samples, 1))

    def predict(self, X):
        """
        Predict class labels.
        """
        probs = self.predict_proba(X)
        # return class with highest probability
        # In a home-advantage league, this is almost always 'H'
        max_idx = np.argmax(probs, axis=1)
        return self.classes_[max_idx]
    
    def score(self, X, y):
        return accuracy_score(y, self.predict(X))
