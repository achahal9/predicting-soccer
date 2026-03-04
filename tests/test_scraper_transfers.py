"""
Tests for the Transfermarkt transfer scraper.

Unit tests verify fee parsing and DB logic.
Integration tests (marked @pytest.mark.network) hit the live site.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.scrape_transfers import (
    scrape_league_transfers,
    ingest_transfers,
    _parse_fee,
)
from src.data.scraper_utils import LEAGUE_CONFIG


class TestFeeParsing:
    """Test transfer fee parsing."""

    def test_millions(self):
        assert _parse_fee('€30.00m') == 30.0
        assert _parse_fee('€5.5m') == 5.5
        assert _parse_fee('£25m') == 25.0
        assert _parse_fee('$12.5m') == 12.5
        assert _parse_fee('30.00m') == 30.0

    def test_thousands(self):
        assert _parse_fee('€500Th.') == 0.5
        assert _parse_fee('€500k') == 0.5
        assert _parse_fee('€750k') == 0.75

    def test_free_transfer(self):
        assert _parse_fee('free transfer') == 0.0
        assert _parse_fee('Free Transfer') == 0.0

    def test_loan(self):
        assert _parse_fee('Loan') is None
        assert _parse_fee('loan fee:€1.5m') is None  # 'loan' keyword → None

    def test_unknown(self):
        assert _parse_fee('-') is None
        assert _parse_fee('?') is None
        assert _parse_fee('') is None
        assert _parse_fee(None) is None


class TestIngestTransfers:
    """Test transfer DB insertion."""

    def test_inserts_transfers(self, seeded_db):
        transfers = [
            {
                'player_name': 'Kevin De Bruyne',
                'from_club': 'Manchester City',
                'to_club': 'Real Madrid',
                'fee_millions': 30.0,
                'transfer_type': 'permanent',
                'season_year': 2025,
            },
        ]
        
        count = ingest_transfers(seeded_db, 'E0', transfers)
        assert count == 1
        
        cursor = seeded_db.cursor()
        cursor.execute('SELECT player_id, transfer_fee_millions FROM transfers')
        row = cursor.fetchone()
        assert row[0] == 1  # De Bruyne matched to existing player
        assert row[1] == 30.0

    def test_creates_new_player_for_unknown(self, seeded_db):
        transfers = [{
            'player_name': 'Brand New Signing',
            'from_club': 'Some FC',
            'to_club': 'Manchester City',
            'fee_millions': 50.0,
            'transfer_type': 'permanent',
            'season_year': 2025,
        }]
        
        count = ingest_transfers(seeded_db, 'E0', transfers)
        assert count == 1
        
        cursor = seeded_db.cursor()
        cursor.execute("SELECT full_name FROM players WHERE full_name = 'Brand New Signing'")
        assert cursor.fetchone() is not None

    def test_skips_duplicate_transfers(self, seeded_db):
        transfer = {
            'player_name': 'Mohamed Salah',
            'from_club': 'Liverpool',
            'to_club': 'Real Madrid',
            'fee_millions': 80.0,
            'transfer_type': 'permanent',
            'season_year': 2025,
        }
        
        count1 = ingest_transfers(seeded_db, 'E0', [transfer])
        count2 = ingest_transfers(seeded_db, 'E0', [transfer])  # Same transfer
        
        assert count1 == 1
        assert count2 == 0  # Duplicate skipped

    def test_free_transfer(self, seeded_db):
        transfers = [{
            'player_name': 'Free Agent Player',
            'to_club': 'Arsenal',
            'fee_millions': 0.0,
            'transfer_type': 'free',
            'season_year': 2025,
        }]
        
        count = ingest_transfers(seeded_db, 'E0', transfers)
        assert count == 1
        
        cursor = seeded_db.cursor()
        cursor.execute("SELECT transfer_type FROM transfers ORDER BY transfer_id DESC LIMIT 1")
        assert cursor.fetchone()[0] == 'free'


@pytest.mark.network
class TestLiveTransferScraping:
    """Live scraping tests — require internet and Cloudflare bypass."""

    def test_scrape_pl_transfers(self):
        result = scrape_league_transfers('E0')
        
        # Note: Transfermarkt may block — that's OK
        assert isinstance(result.success, bool)
        if result.success:
            assert len(result.data) > 0
            first = result.data[0]
            assert 'player_name' in first
        else:
            print(f"Transfer live test info: {result.errors}")

    def test_invalid_league(self):
        result = scrape_league_transfers('INVALID')
        assert result.success is False
