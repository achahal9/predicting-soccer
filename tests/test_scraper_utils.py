"""
Tests for scraper_utils module.

Tests team name normalization, player matching, and rate limiting.
"""

import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.scraper_utils import (
    normalize_team_name,
    get_or_create_team,
    fuzzy_match_player,
    create_player_if_needed,
    rate_limit,
    LEAGUE_CONFIG,
    get_current_season_code,
    ScrapingResult,
)


class TestTeamNameNormalization:
    """Test team name normalization across leagues."""

    def test_premier_league_aliases(self):
        assert normalize_team_name('Man City') == 'Manchester City'
        assert normalize_team_name('Man United') == 'Manchester United'
        assert normalize_team_name('Spurs') == 'Tottenham'
        assert normalize_team_name('Wolves') == 'Wolverhampton'
        assert normalize_team_name("Nott'm Forest") == 'Nottingham Forest'
    
    def test_bundesliga_aliases(self):
        assert normalize_team_name('Bayern München') == 'Bayern Munich'
        assert normalize_team_name('Dortmund') == 'Borussia Dortmund'
        assert normalize_team_name('RB Leipzig') == 'RB Leipzig'
    
    def test_la_liga_aliases(self):
        assert normalize_team_name('FC Barcelona') == 'Barcelona'
        assert normalize_team_name('Real Madrid CF') == 'Real Madrid'
        assert normalize_team_name('Atlético de Madrid') == 'Atletico Madrid'
    
    def test_serie_a_aliases(self):
        assert normalize_team_name('FC Internazionale') == 'Inter'
        assert normalize_team_name('AC Milan') == 'AC Milan'
        assert normalize_team_name('Juventus FC') == 'Juventus'
    
    def test_ligue_1_aliases(self):
        assert normalize_team_name('PSG') == 'Paris Saint-Germain'
        assert normalize_team_name('Olympique Lyonnais') == 'Lyon'
        assert normalize_team_name('AS Monaco') == 'Monaco'
    
    def test_case_insensitive(self):
        assert normalize_team_name('man city') == 'Manchester City'
        assert normalize_team_name('MAN CITY') == 'Manchester City'
    
    def test_unknown_team_returns_original(self):
        assert normalize_team_name('Some Unknown FC') == 'Some Unknown FC'
    
    def test_empty_and_none(self):
        assert normalize_team_name('') == ''
        assert normalize_team_name(None) is None


class TestGetOrCreateTeam:
    """Test team lookup/creation in DB."""

    def test_creates_new_team(self, tmp_db):
        team_id = get_or_create_team(tmp_db, 'Manchester City')
        assert team_id is not None
        assert team_id > 0

    def test_returns_existing_team(self, seeded_db):
        team_id = get_or_create_team(seeded_db, 'Manchester City')
        assert team_id == 1  # First seeded team

    def test_normalizes_before_lookup(self, seeded_db):
        team_id = get_or_create_team(seeded_db, 'Man City')
        assert team_id == 1

    def test_creates_team_from_normalized_name(self, tmp_db):
        team_id = get_or_create_team(tmp_db, 'Spurs')
        # Should create as 'Tottenham'
        cursor = tmp_db.cursor()
        cursor.execute('SELECT team_name FROM teams WHERE team_id = ?', (team_id,))
        assert cursor.fetchone()[0] == 'Tottenham'


class TestFuzzyMatchPlayer:
    """Test player fuzzy matching."""

    def test_exact_match(self, seeded_db):
        result = fuzzy_match_player(seeded_db, 'Kevin De Bruyne')
        assert result == 1  # First seeded player

    def test_case_insensitive_match(self, seeded_db):
        result = fuzzy_match_player(seeded_db, 'kevin de bruyne')
        assert result == 1

    def test_partial_last_name_match(self, seeded_db):
        result = fuzzy_match_player(seeded_db, 'K. De Bruyne')
        assert result == 1

    def test_no_match_returns_none(self, seeded_db):
        result = fuzzy_match_player(seeded_db, 'Nonexistent Player')
        assert result is None

    def test_team_disambiguation(self, seeded_db):
        # Add a second player with similar last name
        cursor = seeded_db.cursor()
        cursor.execute(
            'INSERT INTO players (full_name, position) VALUES (?, ?)',
            ('Haaland Jr', 'CF')
        )
        seeded_db.commit()
        
        # Without team context, should still find original Haaland
        result = fuzzy_match_player(seeded_db, 'E. Haaland', team_id=1)
        assert result == 2  # Erling Haaland (on Man City roster)


class TestCreatePlayerIfNeeded:
    """Test player creation."""
    
    def test_creates_new_player(self, tmp_db):
        player_id = create_player_if_needed(tmp_db, 'New Player', position='GK')
        assert player_id > 0
        
        cursor = tmp_db.cursor()
        cursor.execute('SELECT full_name, position FROM players WHERE master_id = ?', (player_id,))
        row = cursor.fetchone()
        assert row[0] == 'New Player'
        assert row[1] == 'GK'
    
    def test_returns_existing_player(self, seeded_db):
        player_id = create_player_if_needed(seeded_db, 'Kevin De Bruyne')
        assert player_id == 1  # Should not create duplicate


class TestLeagueConfig:
    """Test league configuration."""

    def test_all_five_leagues_present(self):
        assert 'E0' in LEAGUE_CONFIG
        assert 'D1' in LEAGUE_CONFIG
        assert 'SP1' in LEAGUE_CONFIG
        assert 'I1' in LEAGUE_CONFIG
        assert 'F1' in LEAGUE_CONFIG
    
    def test_each_league_has_required_keys(self):
        required = ['name', 'fbref_id', 'fbref_slug', 'tm_id', 'tm_slug']
        for code, config in LEAGUE_CONFIG.items():
            for key in required:
                assert key in config, f"{code} missing '{key}'"


class TestScrapingResult:
    """Test ScrapingResult dataclass."""

    def test_default_state(self):
        r = ScrapingResult(success=False)
        assert r.success is False
        assert r.data == []
        assert r.errors == []
        assert r.records_inserted == 0

    def test_str_representation(self):
        r = ScrapingResult(success=True, data=[{'a': 1}], records_inserted=1)
        s = str(r)
        assert '✓' in s
        assert '1 items' in s


class TestSeasonCode:
    """Test season code generation."""

    def test_returns_4_char_string(self):
        code = get_current_season_code()
        assert len(code) == 4
        assert code.isdigit()


class TestRateLimit:
    """Test rate limiting decorator."""

    def test_delays_execution(self):
        @rate_limit(delay=0.5)
        def fast_func():
            return True
        
        start = time.time()
        fast_func()  # First call — no delay
        fast_func()  # Second call — should delay
        elapsed = time.time() - start
        
        assert elapsed >= 0.4  # Allow small timing variance
