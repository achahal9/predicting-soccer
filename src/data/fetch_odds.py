import pandas as pd
import requests
import io
import datetime

# URL for upcoming fixtures which often contains odds
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"

LEAGUES = ['E0', 'D1', 'SP1', 'I1', 'F1']

def fetch_schedule_with_odds():
    """
    Fetch upcoming schedule and odds from Football-Data.co.uk.
    
    Returns:
        pd.DataFrame: DataFrame with columns: 
                      ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 
                       'B365H', 'B365D', 'B365A']
    """
    print(f"Fetching fixtures from {FIXTURES_URL}...")
    try:
        response = requests.get(FIXTURES_URL)
        response.raise_for_status()
        
        # Read CSV
        # Explicitly decode content to handle BOM
        csv_content = response.content.decode('utf-8-sig')
        df = pd.read_csv(io.StringIO(csv_content), on_bad_lines='skip')
        print("DEBUG: Columns in fixtures.csv:", df.columns.tolist())
        
        # Filter for Top 5 Leagues
        if 'Div' in df.columns:
            print("DEBUG: Unique Divisions found:", df['Div'].unique())
            df = df[df['Div'].isin(LEAGUES)].copy()
        
        # Standardize Columns
        # We need Date, Time, Home, Away, and B365 Odds
        cols_needed = ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A']
        
        # Handle missing Time column (sometimes missing)
        if 'Time' not in df.columns:
            df['Time'] = '00:00'
            
        # Check if odds cols exist
        if 'B365H' not in df.columns:
            print("Warning: Bet365 Home Odds (B365H) not found in fixtures.")
            return pd.DataFrame() # Empty
            
        # Select and Rename if necessary
        # The source usually uses 'HomeTeam', 'AwayTeam' or 'Home', 'Away'
        # It seems it uses 'HomeTeam', 'AwayTeam' based on check script.
        
        df = df[cols_needed]
        
        # Parse Dates (DD/MM/YYYY)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
        # Sort
        df = df.sort_values(['Date', 'Time'])
        
        return df

    except Exception as e:
        print(f"Error fetching upcoming odds: {e}")
        try:
            # If df was created but error happened later
            if 'df' in locals():
                print("Columns found:", df.columns.tolist())
        except:
            pass
        return pd.DataFrame()

if __name__ == "__main__":
    df = fetch_schedule_with_odds()
    if not df.empty:
        print(f"Indices found: {len(df)}")
        print(df.head())
        # Save to potential location for Dashboard
        # df.to_csv('src/data/upcoming_odds.csv', index=False)
    else:
        print("No upcoming odds found for Top 5 leagues.")
