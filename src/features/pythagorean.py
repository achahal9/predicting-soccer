import pandas as pd
import numpy as np

class PythagoreanExpectation:
    def __init__(self, exponent: float = 1.2):
        """
        Args:
            exponent (float): Exponent for the Pythagorean formula.
                              Commonly 1.2-1.7 for soccer.
        """
        self.exponent = exponent

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Pythagorean Expectation for Home and Away teams for each match.
        
        Args:
            df (pd.DataFrame): DataFrame with columns: 
                               'Date', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway'.
                               
        Returns:
            pd.DataFrame: DataFrame with new columns:
                          'PythagoreanHome', 'PythagoreanAway'.
        """
        # Ensure data is sorted by date
        df = df.sort_values('Date').copy()
        
        # We need to track cumulative GF and GA for each team
        # We'll use a dictionary to store current stats for each team
        team_stats = {} # {team_name: {'GF': 0, 'GA': 0}}
        
        pyth_home = []
        pyth_away = []
        
        for _, row in df.iterrows():
            home = row['HomeTeam']
            away = row['AwayTeam']
            
            # Get current stats (before this match)
            stats_home = team_stats.get(home, {'GF': 0, 'GA': 0})
            stats_away = team_stats.get(away, {'GF': 0, 'GA': 0})
            
            # Calculate Expectation
            exp_home = self._calculate_single(stats_home['GF'], stats_home['GA'])
            exp_away = self._calculate_single(stats_away['GF'], stats_away['GA'])
            
            pyth_home.append(exp_home)
            pyth_away.append(exp_away)
            
            # Update stats (after this match)
            # Initialize if new
            if home not in team_stats: team_stats[home] = {'GF': 0, 'GA': 0, 'GP': 0}
            if away not in team_stats: team_stats[away] = {'GF': 0, 'GA': 0, 'GP': 0}
            
            team_stats[home]['GF'] += row['FTHome']
            team_stats[home]['GA'] += row['FTAway']
            team_stats[home]['GP'] += 1
            
            team_stats[away]['GF'] += row['FTAway']
            team_stats[away]['GA'] += row['FTHome']
            team_stats[away]['GP'] += 1
            
        df['PythagoreanHome'] = pyth_home
        df['PythagoreanAway'] = pyth_away
        
        return df

    def _calculate_single(self, gf, ga):
        if gf == 0 and ga == 0:
            return 0.5 # Default probability
        if gf == 0:
            return 0.0
        if ga == 0:
            return 1.0
            
        return (gf ** self.exponent) / (gf ** self.exponent + ga ** self.exponent)
