import pandas as pd
import numpy as np

class FormPythagorean:
    def __init__(self, window: int = 5, exponent: float = 1.2):
        """
        Args:
            window (int): Number of recent games to evaluate for form.
            exponent (float): Exponent for the Pythagorean formula.
                              Commonly 1.2-1.7 for soccer.
        """
        self.window = window
        self.exponent = exponent

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Pythagorean Expectation over a recent window of games.
        
        Args:
            df (pd.DataFrame): DataFrame with columns: 
                               'Date', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'.
                               
        Returns:
            pd.DataFrame: DataFrame with new columns:
                          'FormPythHome', 'FormPythAway'.
        """
        # Ensure data is sorted by date
        df = df.sort_values('Date').copy()
        
        # We need to track recent GF and GA history for each team
        # We'll use a dictionary to store lists of (GF, GA) for each team
        team_history = {} # {team_name: [(gf1, ga1), (gf2, ga2), ...]}
        
        pyth_home = []
        pyth_away = []
        
        for _, row in df.iterrows():
            home = row['HomeTeam']
            away = row['AwayTeam']
            
            # Get current history (before this match)
            hist_home = team_history.get(home, [])
            hist_away = team_history.get(away, [])
            
            # Sum up stats over the window
            home_window_gf = sum([match[0] for match in hist_home[-self.window:]])
            home_window_ga = sum([match[1] for match in hist_home[-self.window:]])
            
            away_window_gf = sum([match[0] for match in hist_away[-self.window:]])
            away_window_ga = sum([match[1] for match in hist_away[-self.window:]])
            
            # Calculate Expectation
            exp_home = self._calculate_single(home_window_gf, home_window_ga)
            exp_away = self._calculate_single(away_window_gf, away_window_ga)
            
            pyth_home.append(exp_home)
            pyth_away.append(exp_away)
            
            # Update history (after this match)
            if home not in team_history: team_history[home] = []
            if away not in team_history: team_history[away] = []
            
            team_history[home].append((row['FTHome'], row['FTAway']))
            team_history[away].append((row['FTAway'], row['FTHome']))
            
        df['FormPythHome'] = pyth_home
        df['FormPythAway'] = pyth_away
        
        return df

    def _calculate_single(self, gf, ga):
        # Allow default probability mostly for very early fixtures or pure 0-0 draws over window
        if gf == 0 and ga == 0:
            return 0.5 
        if gf == 0:
            return 0.0
        if ga == 0:
            return 1.0
            
        return (gf ** self.exponent) / (gf ** self.exponent + ga ** self.exponent)
