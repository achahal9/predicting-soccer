"""
Shared pytest fixtures for scraper tests.

Provides:
- tmp_db: In-memory SQLite database with the full schema
- Fixture HTML files for offline parsing tests
"""

import pytest
import sqlite3
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def tmp_db():
    """
    Create an in-memory SQLite database with the project schema.
    Yields the connection, closes it after the test.
    """
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # Replicate schema.py tables inline for test isolation
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS players (
            master_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date DATE,
            nationality TEXT,
            position TEXT,
            height_cm REAL,
            weight_kg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL UNIQUE,
            country TEXT,
            city TEXT,
            founded_year INTEGER,
            home_stadium TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

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
        );

        CREATE TABLE IF NOT EXISTS transfers (
            transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            from_team_id INTEGER,
            to_team_id INTEGER,
            transfer_date DATE NOT NULL,
            transfer_type TEXT,
            transfer_fee_millions REAL,
            season TEXT,
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(from_team_id) REFERENCES teams(team_id),
            FOREIGN KEY(to_team_id) REFERENCES teams(team_id)
        );

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
        );

        CREATE TABLE IF NOT EXISTS injury_records (
            injury_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_id INTEGER,
            injury_date DATE NOT NULL,
            injury_type TEXT,
            expected_return_date DATE,
            actual_return_date DATE,
            status TEXT DEFAULT 'out',
            severity TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(team_id) REFERENCES teams(team_id)
        );

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
            FOREIGN KEY(player_id) REFERENCES players(master_id),
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            UNIQUE(player_id, team_id, season, league)
        );

        CREATE TABLE IF NOT EXISTS standings (
            standing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            league TEXT NOT NULL,
            position INTEGER,
            played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            goals_for INTEGER DEFAULT 0,
            goals_against INTEGER DEFAULT 0,
            goal_diff INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            snapshot_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(team_id),
            UNIQUE(team_id, season, league, snapshot_date)
        );
    ''')

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(tmp_db):
    """
    tmp_db with sample teams and players pre-loaded.
    """
    cursor = tmp_db.cursor()

    # Teams
    cursor.executemany(
        'INSERT INTO teams (team_name, country) VALUES (?, ?)',
        [
            ('Manchester City', 'England'),
            ('Liverpool', 'England'),
            ('Arsenal', 'England'),
            ('Bayern Munich', 'Germany'),
            ('Real Madrid', 'Spain'),
            ('Inter', 'Italy'),
            ('Paris Saint-Germain', 'France'),
        ]
    )

    # Players
    cursor.executemany(
        'INSERT INTO players (full_name, position) VALUES (?, ?)',
        [
            ('Kevin De Bruyne', 'CM'),
            ('Erling Haaland', 'CF'),
            ('Mohamed Salah', 'RW'),
            ('Bukayo Saka', 'RW'),
            ('Harry Kane', 'CF'),
            ('Lautaro Martinez', 'CF'),
            ('Kylian Mbappe', 'CF'),
        ]
    )

    # Rosters
    cursor.executemany(
        'INSERT INTO team_rosters (team_id, player_id, season) VALUES (?, ?, ?)',
        [
            (1, 1, '2526'), (1, 2, '2526'),  # Man City
            (2, 3, '2526'),                    # Liverpool
            (3, 4, '2526'),                    # Arsenal
            (4, 5, '2526'),                    # Bayern
            (6, 6, '2526'),                    # Inter
            (5, 7, '2526'),                    # Real Madrid
        ]
    )

    tmp_db.commit()
    return tmp_db
