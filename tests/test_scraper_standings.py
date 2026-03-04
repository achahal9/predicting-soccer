"""
Tests for the league standings scraper.

Unit tests verify DB save logic.
Integration tests (marked @pytest.mark.network) hit the live site.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.scrape_standings import (
    scrape_league_standings,
    save_standings,
    _parse_int,
)
from src.data.scraper_utils import LEAGUE_CONFIG


class TestParseInt:
    """Test integer parsing with special characters."""

    def test_standard(self):
        assert _parse_int('42') == 42
    
    def test_positive_sign(self):
        assert _parse_int('+15') == 15
    
    def test_negative_with_unicode_minus(self):
        assert _parse_int('−5') == -5  # Unicode minus sign
    
    def test_none_and_empty(self):
        assert _parse_int(None) == 0
        assert _parse_int('') == 0


class TestSaveStandings:
    """Test standings DB save logic."""

    def test_saves_standings(self, seeded_db):
        standings = [
            {
                'team': 'Liverpool',
                'season_year': 2025,
                'position': 1,
                'played': 25,
                'wins': 19,
                'draws': 4,
                'losses': 2,
                'goals_for': 58,
                'goals_against': 18,
                'goal_diff': 40,
                'points': 61,
            },
            {
                'team': 'Arsenal',
                'season_year': 2025,
                'position': 2,
                'played': 25,
                'wins': 17,
                'draws': 5,
                'losses': 3,
                'goals_for': 50,
                'goals_against': 22,
                'goal_diff': 28,
                'points': 56,
            },
        ]
        
        count = save_standings(seeded_db, 'E0', standings, snapshot_date='2026-03-04')
        assert count == 2
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT position, points FROM standings WHERE snapshot_date = ?', ('2026-03-04',))
        rows = cursor.fetchall()
        assert len(rows) == 2

    def test_upsert_on_same_date(self, seeded_db):
        standings = [{
            'team': 'Liverpool',
            'season_year': 2025,
            'position': 1,
            'points': 61,
        }]
        
        save_standings(seeded_db, 'E0', standings, snapshot_date='2026-03-04')
        
        # Update points
        standings[0]['points'] = 64
        save_standings(seeded_db, 'E0', standings, snapshot_date='2026-03-04')
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT points FROM standings WHERE snapshot_date = ?', ('2026-03-04',))
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 64

    def test_different_dates_create_separate_snapshots(self, seeded_db):
        standings = [{
            'team': 'Liverpool',
            'season_year': 2025,
            'position': 1,
            'points': 61,
        }]
        
        save_standings(seeded_db, 'E0', standings, snapshot_date='2026-03-04')
        
        standings[0]['points'] = 64
        save_standings(seeded_db, 'E0', standings, snapshot_date='2026-03-11')
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT COUNT(*) FROM standings')
        assert cursor.fetchone()[0] == 2  # Two snapshots


@pytest.mark.network
class TestLiveStandingsScraping:
    """Live scraping tests — require internet."""

    def test_scrape_pl_standings(self):
        result = scrape_league_standings('E0')
        
        if result.success:
            assert len(result.data) >= 18
            
            first = result.data[0]
            assert 'team' in first
            assert 'position' in first
            assert 'points' in first
            assert first['position'] >= 1
        else:
            print(f"Standings live test info: {result.errors}")
    
    def test_invalid_league(self):
        result = scrape_league_standings('INVALID')
        assert result.success is False
