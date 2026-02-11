import soccerdata as sd
import pandas as pd
import sqlite3
from pathlib import Path
import time
from datetime import datetime
from src.database.schema import initialize_professional_db

def get_or_create_team(conn, team_name):
    """Get existing team_id or create new team entry."""
    cursor = conn.cursor()
    cursor.execute('SELECT team_id FROM teams WHERE team_name = ?', (team_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    cursor.execute('INSERT INTO teams (team_name, country) VALUES (?, ?)', (team_name, 'England'))
    conn.commit()
    return cursor.lastrowid

def map_player_id(conn, fbref_id, master_id=None):
    """Create or retrieve mapping for a player's FBref ID to master ID."""
    cursor = conn.cursor()
    
    # Check if mapping already exists
    cursor.execute('''
        SELECT master_id FROM id_mapping 
        WHERE entity_type = 'player' AND source_name = 'fbref' AND source_id = ?
    ''', (fbref_id,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # If no mapping exists and no master_id provided, create new player entry
    if master_id is None:
        cursor.execute('INSERT INTO players (full_name) VALUES (?)', (fbref_id,))
        master_id = cursor.lastrowid
    
    # Create the mapping
    cursor.execute('''
        INSERT INTO id_mapping (entity_type, master_id, source_name, source_id, confidence)
        VALUES (?, ?, ?, ?, ?)
    ''', ('player', master_id, 'fbref', fbref_id, 1.0))
    conn.commit()
    return master_id

def ingest_pl_matches(seasons=None, conn=None):
    """Ingest Premier League match results and basic stats."""
    if seasons is None:
        seasons = ["2122", "2223", "2324", "2425"]
    
    if conn is None:
        conn = sqlite3.connect('sports_data.db')
    
    print(f"⚽ Starting FBref ingestion for seasons: {seasons}...")
    fbref = sd.FBref(leagues="ENG-Premier League", seasons=seasons)
    
    try:
        schedule = fbref.read_schedule()
        print("✓ Successfully pulled match schedule.")
    except Exception as e:
        print(f"❌ Error pulling schedule: {e}")
        return
    
    # Filter for played matches
    played_matches = schedule[schedule['result'].notna()].copy()
    
    # Prepare match data with team lookups
    match_data = []
    cursor = conn.cursor()
    
    for idx, row in played_matches.iterrows():
        match_id = idx if isinstance(idx, str) else str(idx)
        home_team_id = get_or_create_team(conn, row['Home'])
        away_team_id = get_or_create_team(conn, row['Away'])
        
        match_data.append({
            'match_id': match_id,
            'date': row['Date'],
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'home_goals': row['Home Goals'],
            'away_goals': row['Away Goals'],
            'season': row['Season'],
            'league': 'ENG-Premier League'
        })
    
    # Insert matches using executemany
    match_df = pd.DataFrame(match_data)
    for _, row in match_df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO match_results 
            (match_id, date, home_team_id, away_team_id, home_goals, away_goals, season, league)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row['match_id'], row['date'], row['home_team_id'], row['away_team_id'],
              row['home_goals'], row['away_goals'], row['season'], row['league']))
    conn.commit()
    
    print(f"✓ Saved {len(match_df)} matches to database")
    return conn

def ingest_pl_squad_stats(seasons=None, conn=None):
    """Ingest Premier League squad rosters and player-level statistics."""
    if seasons is None:
        seasons = ["2122", "2223", "2324", "2425"]
    
    if conn is None:
        conn = sqlite3.connect('sports_data.db')
    
    print(f"📊 Ingesting squad stats for seasons: {seasons}...")
    fbref = sd.FBref(leagues="ENG-Premier League", seasons=seasons)
    cursor = conn.cursor()
    
    try:
        squad_stats = fbref.read_squad_stats()
        print("✓ Successfully pulled squad stats.")
    except Exception as e:
        print(f"❌ Error pulling squad stats: {e}")
        return conn
    
    # Process squad stats
    for season in seasons:
        try:
            season_data = squad_stats[squad_stats.index.get_level_values('Season') == season]
            
            for (team_name, player_name), row in season_data.iterrows():
                team_id = get_or_create_team(conn, team_name)
                
                # Get or create player master record
                fbref_id = f"{player_name}_{team_name}_{season}"
                player_id = map_player_id(conn, fbref_id)
                
                # Update player info if available
                if 'Born' in row.index:
                    cursor.execute('''
                        UPDATE players SET birth_date = ? WHERE master_id = ?
                    ''', (row.get('Born'), player_id))
                
                # Insert player stats
                cursor.execute('''
                    INSERT OR REPLACE INTO player_stats
                    (player_id, team_id, season, league, apps, starts, minutes, 
                     goals, assists, shots, shots_on_target, expected_goals, expected_assists,
                     passing_accuracy, tackles, interceptions, blocks, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player_id, team_id, season, 'ENG-Premier League',
                    row.get('MP', 0), row.get('Starts', 0), row.get('Min', 0),
                    row.get('Gls', 0), row.get('Ast', 0), row.get('Sh', 0), row.get('SoT', 0),
                    row.get('xG', 0.0), row.get('xAG', 0.0),
                    row.get('Pass%', None), row.get('Tkl', 0), row.get('Int', 0),
                    row.get('Clr', 0), datetime.now()
                ))
            conn.commit()
            print(f"✓ Loaded player stats for season {season}")
        except Exception as e:
            print(f"⚠ Error processing season {season}: {e}")
            continue
    
    return conn

def ingest_pl_team_stats(seasons=None, conn=None):
    """Ingest Premier League team-level statistics."""
    if seasons is None:
        seasons = ["2122", "2223", "2324", "2425"]
    
    if conn is None:
        conn = sqlite3.connect('sports_data.db')
    
    print(f"🏆 Ingesting team stats for seasons: {seasons}...")
    fbref = sd.FBref(leagues="ENG-Premier League", seasons=seasons)
    cursor = conn.cursor()
    
    try:
        team_stats = fbref.read_team_stats()
        print("✓ Successfully pulled team stats.")
    except Exception as e:
        print(f"❌ Error pulling team stats: {e}")
        return conn
    
    # Process team stats
    for season in seasons:
        try:
            season_data = team_stats[team_stats.index.get_level_values('Season') == season]
            
            for team_name, row in season_data.iterrows():
                team_id = get_or_create_team(conn, team_name)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO team_stats
                    (team_id, season, league, apps, wins, draws, losses,
                     goals_for, goals_against, expected_goals, expected_goals_against,
                     possession_percent, pass_completion, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_id, season, 'ENG-Premier League',
                    row.get('MP', 0), row.get('W', 0), row.get('D', 0), row.get('L', 0),
                    row.get('GF', 0), row.get('GA', 0), row.get('xG', 0.0), row.get('xGA', 0.0),
                    row.get('Poss', None), row.get('Pass%', None), datetime.now()
                ))
            conn.commit()
            print(f"✓ Loaded team stats for season {season}")
        except Exception as e:
            print(f"⚠ Error processing season {season}: {e}")
            continue
    
    return conn

def run_full_ingestion(seasons=None):
    """Run complete FBref ingestion pipeline."""
    if seasons is None:
        seasons = ["2122", "2223", "2324", "2425"]
    
    # Initialize database schema
    initialize_professional_db()
    
    # Connect to database
    conn = sqlite3.connect('sports_data.db')
    
    # Run ingestion modules
    conn = ingest_pl_matches(seasons, conn)
    conn = ingest_pl_squad_stats(seasons, conn)
    conn = ingest_pl_team_stats(seasons, conn)
    
    conn.close()
    print("✅ FBref ingestion pipeline complete!")

if __name__ == "__main__":
    run_full_ingestion()