import pandas as pd
from typing import List, Optional

def load_matches(filepath: str, 
                 leagues: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Load match data from a CSV file.

    Args:
        filepath (str): Path to the CSV file containing match data.
        leagues (List[str], optional): List of division codes to filter by. 
                                       Defaults to Top 5 European leagues:
                                       ['E0', 'D1', 'SP1', 'I1', 'F1'].

    Returns:
        pd.DataFrame: Loaded and filtered DataFrame.
    """
    if leagues is None:
        # E0: Premier League, D1: Bundesliga, SP1: La Liga, I1: Serie A, F1: Ligue 1
        leagues = ['E0', 'D1', 'SP1', 'I1', 'F1']

    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found at {filepath}")
    except Exception as e:
        raise Exception(f"Error reading CSV file: {e}")

    # Standardize Column Names (strip whitespace just in case)
    df.columns = df.columns.str.strip()

    # Filter by Division
    if leagues:
        df = df[df['Division'].isin(leagues)].copy()

    # Parse Dates
    # The documentation says 'MatchDate' is in YYYY-MM-DD format.
    if 'MatchDate' in df.columns:
        df['Date'] = pd.to_datetime(df['MatchDate'], errors='coerce')
    elif 'Date' in df.columns:
         df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Sort by Date
    if 'Date' in df.columns:
        df = df.sort_values('Date').reset_index(drop=True)

    return df

def preprocess_matches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess match data for modeling.
    
    Args:
        df (pd.DataFrame): Raw dataframe from load_matches.
        
    Returns:
        pd.DataFrame: Cleaned dataframe.
    """
    # ensure we have the target variable 'FTResult'
    if 'FTResult' not in df.columns:
        raise ValueError("DataFrame missing 'FTResult' column")
        
    # Drop rows with missing target or essential team info
    df = df.dropna(subset=['FTResult', 'HomeTeam', 'AwayTeam'])
    
    return df
