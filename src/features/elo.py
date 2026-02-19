import pandas as pd
import numpy as np

class EloFeatures:
    def __init__(self):
        pass

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Elo-based features.
        
        Args:
            df (pd.DataFrame): DataFrame with 'HomeElo', 'AwayElo'.
            
        Returns:
            pd.DataFrame: DataFrame with new columns:
                          'EloDifference', 'EloProbHome', 'EloProbAway'.
        """
        # Ensure copy to avoid SettingWithCopyWarning
        df = df.copy()
        
        if 'HomeElo' not in df.columns or 'AwayElo' not in df.columns:
            # If not present, we can't calculate. Return as is or raise error.
            # Ideally we should merge with EloRatings.csv if missing, but 
            # for now we assume they are in Matches.csv as per schema.
            return df
            
        # Elo Difference (Home - Away)
        # Positive means Home is stronger
        df['EloDifference'] = df['HomeElo'] - df['AwayElo']
        
        # Win Probability
        # P(A) = 1 / (1 + 10^((Rb - Ra) / 400))
        # Here Ra = HomeElo, Rb = AwayElo
        # We calculate Prob(HomeWin)
        df['EloProbHome'] = 1 / (1 + 10 ** ((df['AwayElo'] - df['HomeElo']) / 400))
        df['EloProbAway'] = 1 - df['EloProbHome']
        
        return df
