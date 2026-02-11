import sqlite3

def initialize_professional_db():
    conn = sqlite3.connect('sports_data.db')
    cursor = conn.cursor()

    # === IDENTITY TABLES ===

    # 1. Master Players Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            master_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date DATE,
            nationality TEXT,
            position TEXT,  -- e.g., "CB", "CM", "RW"
            height_cm REAL,
            weight_kg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Master Teams Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL UNIQUE,
            country TEXT,
            city TEXT,
            founded_year INTEGER,
            home_stadium TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Master Managers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS managers (
            manager_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date DATE,
            nationality TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Master Referees Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referees (
            referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date DATE,
            nationality TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. ID Mapping Bridge (Links external source IDs to master IDs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS id_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,  -- 'player', 'team', 'manager', 'referee'
            master_id INTEGER,  -- References respective master table
            source_name TEXT,  -- e.g., 'fbref', 'transfermarkt', 'understat'
            source_id TEXT,    -- External ID from source
            confidence REAL DEFAULT 1.0,  -- 0.0-1.0 confidence score
            notes TEXT,
            UNIQUE(entity_type, source_name, source_id)
        )
    ''')

    # === TEAM & SEASON DATA ===

    # 6. Team Season Rosters (Track squad membership across seasons)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_rosters (
            roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            shirt_number INTEGER,
            joined_date DATE,
            left_date DATE,
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            UNIQUE(team_id, player_id, season)
        )
    ''')

    # 7. Team Manager Assignment (Track manager by season)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_managers (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            start_date DATE,
            end_date DATE,
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            FOREIGN KEY(manager_id) REFERENCES managers(manager_id),
            UNIQUE(team_id, manager_id, season)
        )
    ''')

    # 8. Transfers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            from_team_id INTEGER,
            to_team_id INTEGER,
            transfer_date DATE NOT NULL,
            transfer_type TEXT,  -- 'permanent', 'loan', 'free'
            transfer_fee_millions REAL,
            season TEXT,
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(from_team_id) REFERENCES teams(team_id),
            FOREIGN KEY(to_team_id) REFERENCES teams(team_id)
        )
    ''')

    # === MATCH DATA ===

    # 9. Match Results (Core match information)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_results (
            match_id TEXT PRIMARY KEY,
            date DATE NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_goals INTEGER,
            away_goals INTEGER,
            season TEXT NOT NULL,
            league TEXT NOT NULL,
            match_day INTEGER,
            referee_id INTEGER,
            attendance INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(home_team_id) REFERENCES teams(team_id),
            FOREIGN KEY(away_team_id) REFERENCES teams(team_id),
            FOREIGN KEY(referee_id) REFERENCES referees(referee_id)
        )
    ''')

    # 10. Match Environment (Weather, pitch conditions, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_env (
            match_env_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL UNIQUE,
            temp_celsius REAL,
            precipitation_mm REAL,
            wind_speed_kmh REAL,
            humidity_percent REAL,
            pitch_condition TEXT,  -- 'excellent', 'good', 'poor', etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES match_results(match_id)
        )
    ''')

    # 11. Match Lineups (Track actual starting XI and substitutions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_lineups (
            lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            position TEXT,  -- 'CB', 'CM', 'RW', etc.
            formation_order INTEGER,  -- 1-11 for starters, 12+ for bench
            is_starter BOOLEAN DEFAULT 1,
            minutes_played INTEGER,
            rating REAL,  -- Player performance rating if available
            FOREIGN KEY(match_id) REFERENCES match_results(match_id),
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            UNIQUE(match_id, team_id, player_id)
        )
    ''')

    # === PLAYER PERFORMANCE DATA ===

    # 12. Player Stats (Season-level aggregates)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_stats (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            league TEXT NOT NULL,
            apps INTEGER DEFAULT 0,
            starts INTEGER DEFAULT 0,
            minutes INTEGER DEFAULT 0,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            shots_on_target INTEGER DEFAULT 0,
            expected_goals REAL DEFAULT 0.0,
            expected_assists REAL DEFAULT 0.0,
            passing_accuracy REAL,
            tackles INTEGER DEFAULT 0,
            interceptions INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            clearances INTEGER DEFAULT 0,
            possession_percent REAL,
            rating_avg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            UNIQUE(player_id, team_id, season, league)
        )
    ''')

    # 13. Team Stats (Season-level aggregates)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_stats (
            team_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            league TEXT NOT NULL,
            apps INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            goals_for INTEGER DEFAULT 0,
            goals_against INTEGER DEFAULT 0,
            expected_goals REAL DEFAULT 0.0,
            expected_goals_against REAL DEFAULT 0.0,
            possession_percent REAL,
            pass_completion REAL,
            shots_per_game REAL,
            corners_per_game REAL,
            fouls_per_game REAL,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            UNIQUE(team_id, season, league)
        )
    ''')

    # === INJURY & AVAILABILITY DATA ===

    # 14. Injury Records (Track player injuries and availability)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS injury_records (
            injury_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_id INTEGER,
            injury_date DATE NOT NULL,
            injury_type TEXT,  -- e.g., 'hamstring', 'ligament', 'fracture'
            expected_return_date DATE,
            actual_return_date DATE,
            status TEXT DEFAULT 'out',  -- 'out', 'doubt', 'available'
            severity TEXT,  -- 'minor', 'moderate', 'severe'
            source TEXT,  -- Where the data came from
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(team_id) REFERENCES teams(team_id)
        )
    ''')

    # === CREATE INDEXES FOR PERFORMANCE ===
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_id_mapping_entity ON id_mapping(entity_type, master_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_match_results_date ON match_results(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_match_results_teams ON match_results(home_team_id, away_team_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_match_lineups_match ON match_lineups(match_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfers_player ON transfers(player_id, transfer_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_season ON player_stats(season, league)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_stats_season ON team_stats(season, league)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_injury_records_player ON injury_records(player_id, injury_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_rosters_season ON team_rosters(team_id, season)')

    conn.commit()
    conn.close()
    print("✓ Comprehensive Soccer DB Schema Initialized.")

if __name__ == "__main__":
    initialize_professional_db()