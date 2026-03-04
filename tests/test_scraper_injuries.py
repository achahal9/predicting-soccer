"""
Tests for the Transfermarkt injury scraper.

Unit tests use offline parsing logic.
Integration tests (marked @pytest.mark.network) hit the live site.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.ingest_injuries import (
    add_injury_record,
    get_player_injuries,
    get_team_injuries,
    calculate_injury_impact,
    ingest_scraped_injuries,
    _classify_severity,
    _parse_tm_date,
)


class TestInjurySeverityClassification:
    """Test injury severity classification."""

    def test_severe_injuries(self):
        assert _classify_severity('Cruciate Ligament Rupture') == 'severe'
        assert _classify_severity('ACL Injury') == 'severe'
        assert _classify_severity('Broken Metatarsal') == 'severe'
        assert _classify_severity('Achilles Tendon Rupture') == 'severe'
        assert _classify_severity('Meniscus Injury') == 'severe'

    def test_minor_injuries(self):
        assert _classify_severity('Bruise') == 'minor'
        assert _classify_severity('Illness') == 'minor'
        assert _classify_severity('Flu') == 'minor'
        assert _classify_severity('Dead Leg') == 'minor'
        assert _classify_severity('Rest / Precaution') == 'minor'

    def test_moderate_injuries(self):
        assert _classify_severity('Hamstring Strain') == 'moderate'
        assert _classify_severity('Muscular Problems') == 'moderate'
        assert _classify_severity('Calf Injury') == 'moderate'

    def test_unknown_returns_moderate(self):
        assert _classify_severity('Unknown') == 'moderate'
        assert _classify_severity(None) == 'moderate'
        assert _classify_severity('') == 'moderate'


class TestTmDateParsing:
    """Test Transfermarkt date format parsing."""

    def test_standard_formats(self):
        assert _parse_tm_date('Jan 15, 2026') == '2026-01-15'
        assert _parse_tm_date('15/01/2026') == '2026-01-15'
        assert _parse_tm_date('15.01.2026') == '2026-01-15'
        assert _parse_tm_date('2026-01-15') == '2026-01-15'

    def test_invalid_dates(self):
        assert _parse_tm_date('-') is None
        assert _parse_tm_date('?') is None
        assert _parse_tm_date('') is None
        assert _parse_tm_date(None) is None


class TestInjuryDbOperations:
    """Test injury record CRUD operations."""

    def test_add_injury_record(self, seeded_db):
        injury_id = add_injury_record(
            seeded_db,
            player_id=1,  # Kevin De Bruyne
            injury_date='2026-02-15',
            injury_type='Hamstring',
            expected_return_date='2026-03-15',
            status='out',
            severity='moderate',
            team_id=1,  # Man City
        )
        assert injury_id > 0

    def test_get_player_injuries(self, seeded_db):
        add_injury_record(seeded_db, 1, '2026-01-01', 'Knee', team_id=1)
        add_injury_record(seeded_db, 1, '2026-02-01', 'Hamstring', team_id=1)
        
        injuries = get_player_injuries(seeded_db, 1)
        assert len(injuries) == 2
        
        # With date filter
        injuries_filtered = get_player_injuries(seeded_db, 1, as_of_date='2026-01-15')
        assert len(injuries_filtered) == 1

    def test_get_team_injuries(self, seeded_db):
        add_injury_record(seeded_db, 1, '2026-01-01', 'Knee', team_id=1, status='out')
        add_injury_record(seeded_db, 2, '2026-01-05', 'Ankle', team_id=1, status='out')
        
        team_inj = get_team_injuries(seeded_db, 1)
        assert len(team_inj) == 2

    def test_calculate_injury_impact(self, seeded_db):
        add_injury_record(seeded_db, 1, '2026-01-01', 'Knee', team_id=1, status='out')
        add_injury_record(seeded_db, 2, '2026-01-05', 'Ankle', team_id=1, status='out')
        
        impact = calculate_injury_impact(seeded_db, 1, '2026-02-01')
        assert impact['total_injured'] == 2
        assert len(impact['out_players']) == 2
        assert 0 < impact['impact_score'] < 1.0

    def test_ingest_scraped_injuries(self, seeded_db):
        injuries = [
            {
                'player_name': 'Kevin De Bruyne',
                'team_name': 'Manchester City',
                'injury_type': 'Hamstring',
                'injury_since': '2026-02-20',
                'expected_return': '2026-03-10',
                'status': 'out',
                'severity': 'moderate',
            },
            {
                'player_name': 'New Player XYZ',
                'team_name': 'Liverpool',
                'injury_type': 'Ankle',
                'injury_since': '2026-02-22',
                'status': 'doubt',
                'severity': 'minor',
            },
        ]
        
        count = ingest_scraped_injuries(seeded_db, injuries)
        assert count == 2
        
        # Verify De Bruyne matched existing player
        cursor = seeded_db.cursor()
        cursor.execute('SELECT player_id FROM injury_records WHERE injury_type = ?', ('Hamstring',))
        row = cursor.fetchone()
        assert row[0] == 1  # Kevin De Bruyne's master_id

    def test_duplicate_injury_not_re_inserted(self, seeded_db):
        injury = {
            'player_name': 'Kevin De Bruyne',
            'team_name': 'Manchester City',
            'injury_type': 'Hamstring',
            'injury_since': '2026-02-20',
            'status': 'out',
            'severity': 'moderate',
        }
        
        count1 = ingest_scraped_injuries(seeded_db, [injury])
        count2 = ingest_scraped_injuries(seeded_db, [injury])  # Same injury again
        
        assert count1 == 1
        assert count2 == 0  # Should not re-insert


@pytest.mark.network
class TestLiveInjuryScraping:
    """Live scraping tests — require internet access."""

    def test_scrape_pl_injuries(self):
        from src.data.ingest_injuries import scrape_league_injuries
        
        result = scrape_league_injuries('E0')
        
        # We just check the scraper doesn't crash and returns a result
        assert isinstance(result.success, bool)
        if result.success:
            assert len(result.data) > 0
            # Check structure of first item
            first = result.data[0]
            assert 'player_name' in first
            assert 'injury_type' in first
        else:
            # Transfermarkt may block — that's OK for CI
            print(f"Live test failed (expected if Cloudflare blocks): {result.errors}")
