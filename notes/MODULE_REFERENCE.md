# Module Reference Guide

Quick lookup for all modules and their purposes.

---

## Module Dependency Tree

```
src/main.py (ENTRY POINT)
├──> database/schema.py
│    └── Initializes 14 SQLite tables
│
├──> data/ingest_fbref.py
│    ├── Populates: match_results, players, teams, id_mapping
│    ├── Populates: player_stats, team_stats, team_rosters
│    └── Requires: FBref data via soccerdata library
│
├──> data/ingest_weather.py
│    ├── Populates: match_env (temperature, precipitation, wind, humidity)
│    └── Requires: Open-Meteo API (free)
│
├──> data/ingest_schedule.py
│    ├── Populates: schedule_metrics (rest, fatigue, travel, density)
│    └── Requires: match_results + teams already populated
│
├──> data/ingest_injuries.py
│    ├── Populates: injury_records (player availability)
│    ├── Requires: players + teams already populated
│    └── Status: Template only (scraper not implemented)
│
├──> data/ingest_lineups.py
│    ├── Populates: match_lineups (starting XI, ratings, minutes)
│    ├── Requires: players + teams + match_results
│    └── Status: Template only (parser not complete)
│
├──> database/id_reconciliation.py
│    ├── Reads: id_mapping table
│    ├── Fuzzy matches: players across sources
│    └── Updates: id_mapping with confidence scores
│
└──> processing/feature_engineering.py
     ├── Reads: All database tables
     ├── Computes: 34 features per match
     └── Outputs: training_features.csv
```

---

## Module Responsibilities

### **Data Ingestion Layer**

#### `src/data/ingest_fbref.py`
**Purpose:** Fetch match results, player stats, team stats from FBref  
**Public Functions:**
- `run_full_ingestion(seasons)` — Main entry point
- `ingest_pl_matches(seasons, conn)` — Match results
- `ingest_pl_squad_stats(seasons, conn)` — Player stats
- `ingest_pl_team_stats(seasons, conn)` — Team aggregates
- `get_or_create_team(conn, team_name)` — Team ID lookup/creation
- `map_player_id(conn, fbref_id, master_id)` — Player ID mapping

**Data Source:** FBref.com via `soccerdata` library  
**Frequency:** Monthly (new match weeks)  
**Duration:** ~2-3 minutes

---

#### `src/data/ingest_weather.py`
**Purpose:** Fetch weather conditions for each match  
**Public Functions:**
- `ingest_historical_weather(conn, start_date, end_date)` — Backfill weather
- `ingest_match_weather(conn, match_id, team_name, match_date)` — Single match
- `fetch_historical_weather(lat, lon, start_date, end_date)` — Raw API call
- `fetch_forecast_weather(lat, lon, forecast_days)` — Future predictions
- `get_match_weather(conn, match_id)` — Retrieve stored weather

**Data Source:** Open-Meteo API (free, no authentication)  
**Frequency:** On-demand or daily for 7-day forecast  
**Duration:** ~30 seconds per match

---

#### `src/data/ingest_schedule.py`
**Purpose:** Compute team fatigue & schedule congestion metrics  
**Public Functions:**
- `build_schedule_metrics_table(conn)` — Compute for all matches
- `calculate_days_rest(conn, team_id, match_date)` — Days since last match
- `calculate_match_density(conn, team_id, match_date, days)` — Matches in period
- `calculate_fatigue_score(conn, team_id, match_date)` — Composite 0-1 score
- `calculate_consecutive_away_matches(conn, team_id, match_date)` — Away streak
- `get_travel_distance(from_team, to_team)` — Stadium distance (km)

**Data Source:** match_results + teams tables (computed)  
**Frequency:** When new matches added  
**Duration:** ~1 minute for all matches

---

#### `src/data/ingest_injuries.py`
**Purpose:** Track player injuries and availability  
**Public Functions:**
- `ingest_injuries(conn, source)` — Main entry (template)
- `add_injury_record(conn, player_id, injury_date, ...)` — Insert injury
- `update_injury_status(conn, injury_id, status, ...)` — Update status
- `get_team_injuries(conn, team_id, as_of_date, status_filter)` — Team's injured players
- `calculate_injury_impact(conn, team_id, as_of_date)` — Impact score 0-1
- `get_player_injuries(conn, player_id, as_of_date)` — Player history

**Data Source:** Transfermarkt (scraper not implemented)  
**Status:** Ready to use, but requires external data population  
**Frequency:** Daily (injury status changes frequently)  
**Duration:** Depends on scraper implementation

---

#### `src/data/ingest_lineups.py`
**Purpose:** Store historical starting XI and player ratings  
**Public Functions:**
- `ingest_pl_lineups(seasons, conn)` — Main entry (partial)
- `ingest_lineup_from_match_report(conn, match_id, team_id, lineup_data)` — Insert lineup
- `get_match_lineups(conn, match_id, team_id)` — Retrieve starting XI
- `get_starting_xi(conn, match_id, team_id)` — Just the 11 starters
- `analyze_team_frequent_lineups(conn, team_id, season)` — Most common formation
- `map_player_to_master_id(conn, player_name, team_id, fbref_id)` — Player mapping

**Data Source:** FBref match reports via `soccerdata`  
**Status:** Template ready, parser needs enhancement  
**Frequency:** As you add new matches  
**Duration:** ~1-2 minutes for all matches

---

### **Database Layer**

#### `src/database/schema.py`
**Purpose:** Define SQLite schema and initialize database  
**Public Functions:**
- `initialize_professional_db()` — Create all 14 tables + indexes

**Tables Created:**
1. `players` — Master player records
2. `teams` — Master team records
3. `managers` — Manager records
4. `referees` — Referee records
5. `id_mapping` — Cross-source ID linking
6. `team_rosters` — Player-to-team assignments by season
7. `team_managers` — Manager-to-team assignments by season
8. `transfers` — Player transfer history
9. `match_results` — Match facts (scores, dates, teams)
10. `match_env` — Match environment (weather, attendance)
11. `match_lineups` — Starting XI and player ratings per match
12. `player_stats` — Player season aggregates (goals, xG, etc.)
13. `team_stats` — Team season aggregates
14. `injury_records` — Player injuries and status

**Indexes:** 9 indexes for common queries

---

#### `src/database/id_reconciliation.py`
**Purpose:** Deduplicate players across data sources  
**Public Functions:**
- `reconcile_players_across_sources(conn, auto_merge_threshold, auto_merge)` — Main
- `match_players_across_sources(conn, source1, source2)` — Find matches
- `merge_player_records(conn, master_id_keep, master_id_remove, data)` — Merge
- `find_duplicate_players(conn, name_threshold)` — Find local duplicates
- `audit_id_mappings(conn)` — Coverage report
- `get_unreconciled_players(conn)` — Players with 1 source ID

**Algorithm:** Fuzzy string matching (SequenceMatcher) + birth date verification  
**Confidence:** 0-1 score (1.0 = highly confident)  
**Duration:** ~30 seconds for 800+ players

---

### **Processing Layer**

#### `src/processing/metrics.py`
**Purpose:** Soccer analytics and domain metrics  
**Public Functions:**
- `calculate_pythagorean_expectation(gf, ga, exponent)` — Expected win %
- `get_performance_gap(actual, expected)` — Luck metric
- `calculate_shot_efficiency(goals, shots)` — Conversion rate
- `calculate_expected_goals_efficiency(xG, actual_goals)` — Clinical finishing
- `analyze_head_to_head(conn, team1_id, team2_id, limit)` — Historical H2H
- `calculate_defensive_strength(ga, matches)` — Defense rating
- `calculate_attacking_strength(gf, matches)` — Attack rating
- `analyze_team_consistency(conn, team_id, season, metric)` — Variance
- `get_formation_analysis(conn, team_id, season)` — Formation frequencies
- `calculate_home_away_split(conn, team_id, season)` — Home vs away
- `compatibility_score(player_stats1, player_stats2)` — Player fit (template)

---

#### `src/processing/feature_engineering.py`
**Purpose:** Build ML-ready feature matrix  
**Public Functions:**
- `build_training_dataset(conn, season_filter, include_incomplete)` — Main output
- `build_match_features(conn, match_id)` — Features for 1 match
- `get_team_recent_form(conn, team_id, match_date, lookback)` — Form metrics
- `get_team_aggregated_stats(conn, team_id, season)` — Season stats
- `get_injury_impact(conn, team_id, match_date)` — Injury count + score
- `get_weather_for_match(conn, match_id)` — Weather conditions
- `get_schedule_metrics(conn, match_id)` — Fatigue + rest + travel
- `get_squad_quality(conn, team_id, match_id, match_date)` — Player quality

**Output:** DataFrame with 34 columns per match  
**Time:** ~2 seconds for 380 matches  
**Output File:** `training_features.csv`

---

### **Orchestration**

#### `src/main.py`
**Purpose:** Command-line interface to run pipeline phases  
**Public Functions:**
- `main()` — CLI entry point
- `run_full_pipeline(seasons, include_features)` — Run all phases
- `run_data_ingestion(seasons)` — Phase 1
- `run_id_reconciliation()` — Phase 2
- `run_feature_engineering(season_filter)` — Phase 3
- `init_database()` — Phase 0

**Usage:**
```bash
python -m src.main --phase all --seasons 2122 2223 2324 2425
python -m src.main --phase ingest --verbose
python -m src.main --phase features --skip-features
```

---

## Import Reference

### **From Data Layer**
```python
from src.data.ingest_fbref import run_full_ingestion, ingest_pl_matches
from src.data.ingest_injuries import ingest_injuries, get_team_injuries
from src.data.ingest_weather import ingest_historical_weather, get_match_weather
from src.data.ingest_schedule import calculate_fatigue_score, build_schedule_metrics_table
from src.data.ingest_lineups import ingest_pl_lineups, get_match_lineups
```

### **From Database Layer**
```python
from src.database.schema import initialize_professional_db
from src.database.id_reconciliation import reconcile_players_across_sources, audit_id_mappings
```

### **From Processing Layer**
```python
from src.processing.metrics import (
    calculate_pythagorean_expectation,
    analyze_head_to_head,
    calculate_home_away_split
)
from src.processing.feature_engineering import build_training_dataset, build_match_features
```

---

## Function Signatures Quick Reference

```python
# Data Ingestion
run_full_ingestion(seasons=['2122', '2223', '2324', '2425']) -> None
ingest_injuries(conn: sqlite3.Connection, source='transfermarkt') -> None
ingest_historical_weather(conn, start_date='2021-01-01', end_date=None) -> None
build_schedule_metrics_table(conn: sqlite3.Connection) -> None

# Database
initialize_professional_db() -> None
reconcile_players_across_sources(conn, auto_merge_threshold=0.95, auto_merge=False) -> None
audit_id_mappings(conn: sqlite3.Connection) -> Dict

# Metrics
calculate_pythagorean_expectation(goals_for: int, goals_against: int, exponent=1.35) -> float
analyze_head_to_head(conn, team1_id, team2_id, limit=None) -> Dict
calculate_fatigue_score(conn, team_id, match_date) -> float

# Feature Engineering
build_training_dataset(conn, season_filter=None, include_incomplete=False) -> pd.DataFrame
build_match_features(conn, match_id) -> Optional[Dict]
get_team_recent_form(conn, team_id, match_date, lookback_matches=5) -> Dict
```

---

## Common Workflows

### **Workflow 1: Run Complete Pipeline**
```python
from src.main import run_full_pipeline
run_full_pipeline(seasons=['2425'], include_features=True)
# Output: sports_data.db + training_features.csv
```

### **Workflow 2: Analyze Single Team**
```python
import sqlite3
from src.processing.metrics import analyze_head_to_head

conn = sqlite3.connect('sports_data.db')
city_id = 1  # Manchester City
h2h = analyze_head_to_head(conn, city_id, city_id+1)
print(f"Record: {h2h['team1_wins']}-{h2h['team1_draws']}-{h2h['team1_losses']}")
```

### **Workflow 3: Check Data Quality**
```python
import sqlite3
from src.database.id_reconciliation import audit_id_mappings

conn = sqlite3.connect('sports_data.db')
audit = audit_id_mappings(conn)
print(f"ID Coverage: {audit['coverage_percent']}%")
```

### **Workflow 4: Compute Team Fatigue**
```python
import sqlite3
from src.data.ingest_schedule import calculate_fatigue_score

conn = sqlite3.connect('sports_data.db')
fatigue = calculate_fatigue_score(conn, team_id=1, match_date='2025-02-15')
print(f"Fatigue: {fatigue:.2f}")  # 0=fresh, 1=exhausted
```

### **Workflow 5: Get Training Features**
```python
import pandas as pd
from src.processing.feature_engineering import build_training_dataset
import sqlite3

conn = sqlite3.connect('sports_data.db')
features = build_training_dataset(conn)
print(f"Shape: {features.shape}")  # (380, 34)
features.to_csv('training_features.csv')
```

---

## Logging & Debugging

All modules use Python's `logging` module:

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("User-friendly progress message")
logger.warning("Potential data issue (non-fatal)")
logger.error("Something failed (but continue?)")
```

**Enable verbose logging:**
```bash
python -m src.main --verbose
```

---

## Testing

```bash
# Run all tests
pytest tests/
pytest tests/ -v  # Verbose
pytest tests/ -x  # Stop on first failure

# Test specific module
pytest tests/test_metrics.py -v
```

---

## Configuration

**Static Config:** `config/leagues.yaml`
```yaml
leagues:
  ENGLAND:
    id: ENG-Premier League
    seasons: ["2122", "2223", "2324", "2425"]
    exponent: 1.35
```

**Programmatic Config:** In each ingestion module
```python
# ingest_fbref.py
seasons = ["2122", "2223", "2324", "2425"]
league_name = "ENG-Premier League"
```

---

## Performance Tuning

| Bottleneck | Mitigation |
|-----------|-----------|
| FBref scraping slow | Use cached .soccerdata folder |
| Feature engineering slow | Cache intermediate results |
| ID reconciliation slow | Parallelize fuzzy matching (future) |
| Database queries slow | Ensure indexes are created |

```python
# Use database indexes
conn.execute("SELECT * FROM match_results WHERE date = ?", ('2025-02-15',))
# Fast ✓

conn.execute("SELECT * FROM match_results WHERE home_goals = 2")
# Slow ✗ (no index on home_goals)
```

---

## Next Steps

1. **Understand flow:** Read this file + [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Try it:** Run `python -m src.main --phase all`
3. **Explore data:** `training_features.csv` or notebooks
4. **Extend:** Copy a template module, modify, integrate
5. **Deploy:** Build API endpoint around feature building

---

See [README.md](README.md), [QUICKSTART.md](QUICKSTART.md), [FEATURES.md](FEATURES.md) for more details.
