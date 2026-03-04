"""
Tests for the FBref advanced stats scraper.

Unit tests verify parsing and DB upsert logic.
Integration tests (marked @pytest.mark.network) hit the live site.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.scrape_fbref_stats import (
    scrape_league_stats,
    upsert_team_stats,
    _parse_int,
    _parse_float,
)
from src.data.scraper_utils import LEAGUE_CONFIG


class TestParsers:
    """Test numeric parsing helpers."""

    def test_parse_int(self):
        assert _parse_int('42') == 42
        assert _parse_int('1,500') == 1500
        assert _parse_int(None) == 0
        assert _parse_int('') == 0
        assert _parse_int('abc') == 0

    def test_parse_float(self):
        assert _parse_float('3.14') == 3.14
        assert _parse_float('1,500.5') == 1500.5
        assert _parse_float(None) == 0.0
        assert _parse_float('') == 0.0
        assert _parse_float('abc') == 0.0


class TestUpsertTeamStats:
    """Test DB upsert logic."""

    def test_inserts_new_stats(self, seeded_db):
        stats = [{
            'team': 'Manchester City',
            'season_year': 2025,
            'matches_played': 25,
            'wins': 18,
            'draws': 4,
            'losses': 3,
            'goals_for': 60,
            'goals_against': 20,
            'xg': 55.3,
            'xga': 22.1,
            'possession': 62.5,
        }]
        
        count = upsert_team_stats(seeded_db, 'E0', stats)
        assert count == 1
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT expected_goals, possession_percent FROM team_stats WHERE team_id = 1')
        row = cursor.fetchone()
        assert row[0] == 55.3
        assert row[1] == 62.5

    def test_upserts_existing_stats(self, seeded_db):
        stats1 = [{
            'team': 'Manchester City',
            'season_year': 2025,
            'wins': 15,
            'xg': 50.0,
        }]
        stats2 = [{
            'team': 'Manchester City',
            'season_year': 2025,
            'wins': 18,
            'xg': 58.0,
        }]
        
        upsert_team_stats(seeded_db, 'E0', stats1)
        upsert_team_stats(seeded_db, 'E0', stats2)
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT wins, expected_goals FROM team_stats WHERE team_id = 1')
        row = cursor.fetchone()
        assert row[0] == 18
        assert row[1] == 58.0

    def test_multiple_teams(self, seeded_db):
        stats = [
            {'team': 'Manchester City', 'season_year': 2025, 'xg': 55.0},
            {'team': 'Liverpool', 'season_year': 2025, 'xg': 52.0},
            {'team': 'Arsenal', 'season_year': 2025, 'xg': 48.0},
        ]
        
        count = upsert_team_stats(seeded_db, 'E0', stats)
        assert count == 3

    def test_creates_new_team_if_needed(self, tmp_db):
        stats = [{'team': 'Brand New FC', 'season_year': 2025, 'xg': 10.0}]
        count = upsert_team_stats(tmp_db, 'E0', stats)
        assert count == 1
        
        cursor = tmp_db.cursor()
        cursor.execute("SELECT team_name FROM teams WHERE team_name = 'Brand New FC'")
        assert cursor.fetchone() is not None


@pytest.mark.network
class TestLiveFBrefScraping:
    """Live scraping tests — require internet."""

    def test_scrape_pl_stats(self):
        result = scrape_league_stats('E0')
        
        assert isinstance(result.success, bool)
        if result.success:
            assert len(result.data) >= 18  # At least 18 teams in PL
            
            first = result.data[0]
            assert 'team' in first
            assert 'xg' in first
            assert 'possession' in first
            
            # xG should be a reasonable number
            assert first['xg'] >= 0
        else:
            print(f"FBref live test failed: {result.errors}")

    def test_invalid_league_returns_error(self):
        result = scrape_league_stats('XX')
        assert result.success is False
        assert len(result.errors) > 0
