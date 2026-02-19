import pandas as pd
import numpy as np

class LaggedStats:
    def __init__(self, window: int = 5):
        self.window = window
        self.features_map = {
            'Goals': ('FTHome', 'FTAway'),
            'Shots': ('HomeShots', 'AwayShots'),
            'SoT': ('HomeTarget', 'AwayTarget'),
            'Corners': ('HomeCorners', 'AwayCorners'),
            'Fouls': ('HomeFouls', 'AwayFouls'),
            'YellowCards': ('HomeYellow', 'AwayYellow'),
            'RedCards': ('HomeRed', 'AwayRed')
        }

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rolling average stats for Home and Away teams.
        """
        df = df.sort_values('Date').copy()
        
        # We need a history for every team for every feature
        team_history = {} 
        
        # Prepare storage for new columns
        new_cols = {}
        for feat in self.features_map.keys():
            new_cols[f'Home{feat}Avg'] = []
            new_cols[f'Away{feat}Avg'] = []
        
        # Iterate matches
        # This loop is unavoidable for "stateful" transformations where
        # row N depends on the *processed* history of teams in row N.
        # But for simple rolling windows, we just need the history list.
        
        for _, row in df.iterrows():
            home = row['HomeTeam']
            away = row['AwayTeam']
            
            # --- READ HISTORICAL STATS ---
            for feat in self.features_map.keys():
                # Get history or empty list
                hist_home = team_history.get(home, {}).get(feat, [])
                hist_away = team_history.get(away, {}).get(feat, [])
                
                # Calculate Average (if enough history, else global avg or 0)
                # We can require at least 1 game, or return NaN
                val_home = np.mean(hist_home[-self.window:]) if hist_home else np.nan
                val_away = np.mean(hist_away[-self.window:]) if hist_away else np.nan
                
                new_cols[f'Home{feat}Avg'].append(val_home)
                new_cols[f'Away{feat}Avg'].append(val_away)
            
            # --- UPDATE HISTORY (Post-match) ---
            for feat, (col_home, col_away) in self.features_map.items():
                if home not in team_history: team_history[home] = {}
                if away not in team_history: team_history[away] = {}
                if feat not in team_history[home]: team_history[home][feat] = []
                if feat not in team_history[away]: team_history[away][feat] = []
                
                # Append current match stats
                # Handle possible NaNs in source data by defaulting to 0 or skipping?
                # Data loader should have handled NaNs but let's be safe
                val_h = row.get(col_home, 0)
                val_a = row.get(col_away, 0)
                
                # Check for NaN in the row data itself
                if pd.isna(val_h): val_h = 0
                if pd.isna(val_a): val_a = 0

                team_history[home][feat].append(val_h)
                team_history[away][feat].append(val_a)
                
        # Add new columns to DF
        for col_name, data in new_cols.items():
            df[col_name] = data
            
        return df
