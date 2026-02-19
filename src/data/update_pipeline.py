import pandas as pd
import requests
import os
from datetime import datetime
import io
import argparse

# Constants
DATA_DIR = os.path.join('src', 'data', 'historicaldata2000-25')
MATCHES_FILE = os.path.join(DATA_DIR, 'Matches.csv')

# Valid Top 5 Leagues on football-data.co.uk
# 2025/2026 season usually encoded as '2526' in URL
# Current logic assumes we are looking for the "current" season.
# Dynamic season detection to be robust.
def get_season_string():
    now = datetime.now()
    # Simple logic: if month > 7, we are in start of season YYYY/(YY+1)
    # if month <= 7, we are in end of season (YY-1)/YY
    year = now.year
    if now.month > 7:
        start = year % 100
        end = (year + 1) % 100
    else:
        start = (year - 1) % 100
        end = year % 100
    return f"{start:02d}{end:02d}"

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"

LEAGUES = ['E0', 'D1', 'SP1', 'I1', 'F1']

def fetch_league_data(div, season):
    url = BASE_URL.format(season=season, div=div)
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.text), on_bad_lines='skip')
    except Exception as e:
        print(f"Failed to fetch {div} for season {season}: {e}")
        return None

def update_matches(manual_mode=False):
    print(f"Loading existing matches from {MATCHES_FILE}...")
    try:
        existing_df = pd.read_csv(MATCHES_FILE)
        # Parse dates to ensure comparison works
        # Try 'Date' then 'MatchDate'
        date_col = 'Date' if 'Date' in existing_df.columns else 'MatchDate'
        existing_df[date_col] = pd.to_datetime(existing_df[date_col], errors='coerce')
        
        last_date = existing_df[date_col].max()
        print(f"Latest match in DB: {last_date}")
        
    except FileNotFoundError:
        print("Matches file not found. Starting fresh? (Not implemented for safety)")
        return

    season = get_season_string()
    print(f"Fetching data for season code: {season}")
    
    new_matches = []
    
    for div in LEAGUES:
        print(f"Checking {div}...")
        df_new = fetch_league_data(div, season)
        
        if df_new is not None and not df_new.empty:
            # Standardize Date
            # Football-Data usually DD/MM/YYYY or DD/MM/YY
            df_new['Date'] = pd.to_datetime(df_new['Date'], dayfirst=True, errors='coerce')
            
            # Filter matches newer than last_date
            # Only if last_date is valid
            if pd.notna(last_date):
                update_df = df_new[df_new['Date'] > last_date]
            else:
                update_df = df_new
                
            if not update_df.empty:
                print(f"Found {len(update_df)} new matches for {div}.")
                # Add Division column if missing
                if 'Division' not in update_df.columns and 'Div' in update_df.columns:
                     update_df['Division'] = update_df['Div']
                
                new_matches.append(update_df)
            else:
                print(f"No new matches for {div}.")
    
    if new_matches:
        all_new = pd.concat(new_matches, ignore_index=True)
        print(f"Total new matches found: {len(all_new)}")
        
        # Align columns (basic)
        # We might need to map columns if naming changed, but football-data is usually stable.
        # We append to existing_df
        # Use pd.concat
        updated_df = pd.concat([existing_df, all_new], ignore_index=True)
        
        # Sort
        updated_df = updated_df.sort_values(date_col).reset_index(drop=True)
        
        # Save
        if manual_mode:
            print("Saving updated file...")
            updated_df.to_csv(MATCHES_FILE, index=False)
            print("Done.")
        else:
            print("Dry run mode (script default). Use --manual to save.")
            print("New matches tail:")
            print(all_new.head())
            
            # For CI/CD, we might want to automatically save if a flag is passed
            # Let's support a --save flag
    else:
        print("No updates required.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--manual', action='store_true', help="Manual mode: Save changes locally.")
    parser.add_argument('--save', action='store_true', help="Save changes (for CI/CD).")
    args = parser.parse_args()
    
    # manual or save -> write to disk
    write_changes = args.manual or args.save
    update_matches(manual_mode=write_changes)
