
# System Architecture

## Overview

Soccer Prediction System follows a **modular, phased architecture** emphasizing:
- **Data integrity**: All entities tracked by unique master IDs with cross-source mapping
- **Extensibility**: Support for multiple leagues/data sources with minimal changes
- **Auditability**: Every data point has provenance (source, confidence score, timestamp)
- **Offline capability**: Works with cached data; updates are incremental

---

## Core Design Patterns

### **1. Master ID Pattern**

All entities have a **master record** + **source-specific mappings**:

```
Master Players Table
├── master_id: 1001
├── full_name: "Harry Kane"
├── birth_date: 1993-07-28
└── nationality: "England"

ID Mappings
├── (entity='player', master_id=1001, source='fbref', source_id='d70ce98e', confidence=1.0)
├── (entity='player', master_id=1001, source='transfermarkt', source_id='44625', confidence=0.95)
└── (entity='player', master_id=1001, source='understat', source_id='564', confidence=0.92)
```

**Benefits:**
- Handles player name variations across sources
- Tracks transfer history (attach stints to same master_id)
- Supports retrospective data merges with confidence tracking
- Easy multi-league setup (different sources per league)

---

### **2. Separation of Concerns**

```
src/
├── data/              # Data Ingestion Layer
│   ├── ingest_fbref.py           # Match stats, player stats, rosters
│   ├── ingest_injuries.py        # Availability tracking
│   ├── ingest_weather.py         # Contextual weather
│   ├── ingest_schedule.py        # Schedule health metrics
│   └── ingest_lineups.py         # Historical starting XI
│
├── database/          # Data Persistence Layer
│   ├── schema.py                 # SQLite schema definition
│   └── id_reconciliation.py      # Cross-source deduplication
│
├── processing/        # Analytics & Feature Layer
│   ├── metrics.py                # Domain metrics (Pythagorean, etc.)
│   └── feature_engineering.py    # ML-ready feature matrix
│
└── main.py            # Orchestration & Entrypoint
```

---

### **3. Layered Data Flow**

```
RAW DATA LAYER (Ingestion)
├── FBref JSON/HTML
├── Open-Meteo API responses
├── Transfermarkt HTML
└── Match calendar

↓ Normalize & Validate

NORMALIZED LAYER (Database)
├── players (identity)
├── match_results (facts)
├── team_stats (aggregates)
├── injury_records (state)
└── schedule_metrics (derived)

↓ Enrich & Cross-reference

FEATURE LAYER (ML Ready)
├── training_features.csv
├── team_form metrics
├── player quality scores
└── contextual features
```

---

## Database Schema

### **14 Tables, 6 Relationships**

```
IDENTITY TABLES
├── players (master_id PK)
│   └── id_mapping (maps fbref → master)
│
├── teams (team_id PK)
│
├── managers (manager_id PK)
│
└── referees (referee_id PK)

CAREER TRACKING
├── team_rosters (team_id, player_id, season)
│   └── Links players to teams across history
│
├── team_managers (team_id, manager_id, season)
│   └── Tracks manager tenure
│
└── transfers (player_id, from_team_id, to_team_id, date)
    └── Complete transfer history

MATCH DATA
├── match_results (match_id PK)
│   ├── FK: home_team_id, away_team_id, referee_id
│   ├── Facts: date, score, attendance
│   └── Always normalized (no "Arsenal" strings)
│
├── match_env (match_id FK)
│   └── Weather & pitch conditions
│
└── match_lineups (match_id, team_id, player_id FK)
    ├── Actual starting XI
    └── Player ratings per match

PERFORMANCE DATA
├── player_stats (player_id, team_id, season FK)
│   └── Aggregates: apps, goals, xG, pass%, etc.
│
├── team_stats (team_id, season FK)
│   └── Season totals: W-D-L, xG, possession, etc.
│
└── injury_records (player_id FK)
    └── Status: out/doubt/available with dates

DERIVED DATA
├── schedule_metrics (match_id FK)
│   ├── rest days, match density, travel distance
│   └── Computed by ingest_schedule.py
│
└── training_features (match_id FK)
    ├── Full feature vector for ML
    └── Built by feature_engineering.py
```

---

## Data Validation Strategy

### **Constraints & Checks**

1. **Referential Integrity** (SQL Foreign Keys)
   - All team_ids must exist in teams table
   - All player_ids must exist in players table
   - No orphaned records

2. **Domain-Specific Validation**
   ```python
   # In ingest_fbref.py
   assert 0 <= goals <= 10, "Unrealistic goal count"
   assert match_date >= season_start, "Match before season"
   assert home_team != away_team, "Team can't play itself"
   ```

3. **ID Mapping Confidence** (0-1 score)
   - 1.0 = Direct match (same ID across sources)
   - 0.95+ = Auto-merge in reconciliation
   - 0.80-0.94 = Require manual review
   - <0.80 = Not merged

4. **Logging & Auditing**
   - Every insert/update includes timestamp
   - Source and confidence tracked
   - Missing data logged warning (not error)

### **Data Quality Report**

```python
from src.database.id_reconciliation import audit_id_mappings

audit = audit_id_mappings(conn)
# Output:
# {
#   'total_players': 850,
#   'mapped_players': 821,
#   'coverage_percent': 96.6,
#   'by_source': {'fbref': 850, 'transfermarkt': 450, 'understat': 380}
# }
```

---

## Feature Engineering Pipeline

### **Match-Level Features** (~35 dimensions)

```
TEAM FORM (per team)
├── wins, draws, losses (last 5 matches)
├── goals_for, goals_against
├── expected_goals, expected_goals_against
└── points_per_game, win_percentage

SEASON STATS (per team)
├── wins_season, goals_for_season
├── expected_goals_season, possession
└── pass_completion

SCHEDULE HEALTH (per team)
├── days_rest_since_last_match
├── match_density_14d (rolling)
├── fatigue_score (0-1)
└── consecutive_away_matches

CONTEXTUAL (per match)
├── temperature, precipitation, wind_speed, humidity
├── away_travel_distance_km
└── injury_impact_score (% of squad out)

SQUAD QUALITY (per team)
├── squad_avg_rating (if lineups available)
├── squad_avg_apps (experience)
└── player_turnover (transfers)

TARGET VARIABLE
└── outcome: home_win | draw | away_win
```

### **Feature Generation Code**

```python
# 1 feature vector per match (34)
from src.processing.feature_engineering import build_match_features

features = build_match_features(conn, match_id='match_123')
# Returns dict with all features + target

# Build full training dataset
from src.processing.feature_engineering import build_training_dataset

dataset = build_training_dataset(conn, season_filter='2425')
# Returns DataFrame (N_matches x 34 cols) ready for sklearn
dataset.to_csv('training_features.csv')
```

---

## Ingestion Strategies

### **Incremental vs. Full**

**FBref Ingestion** (ingest_fbref.py)
- Strategy: Incremental (append new seasons, don't re-scrape)
- Frequency: Monthly (new match weeks)
- Cache: `.soccerdata/` folder (auto-managed by soccerdata library)
- Syntax: `INSERT OR IGNORE` on match_id (PK prevents duplicates)

**Weather Ingestion** (ingest_weather.py)
- Strategy: Backfill first, then add upcoming
- Frequency: Daily (for next 7 days forecast)
- API: Open-Meteo (free, no rate limits with reason)
- Caching: Store in match_env table

**Injury Ingestion** (ingest_injuries.py)
- Strategy: Daily refresh (status changes frequently)
- Source: Transfermarkt (requires scraper—currently template)
- Manual fallback: CSV upload
- TODO: Implement web scraper or use paid API

---

## Extensibility Points

### **Adding a New Data Source**

Example: Add Understat xG data

```python
# 1. Create src/data/ingest_understat.py
def ingest_understat_xg(conn, seasons=['2425']):
    """Fetch and store Understat xG overrides."""
    # Fetch data
    understat = fetch_understat_api(seasons)
    
    # 2. Add/Update ID mappings
    for stat in understat:
        player_id = map_player_id(
            conn, fbref_id=stat['fbref_id'],
            source_name='understat', source_id=stat['understat_id']
        )
    
    # 3. Store in player_stats with new columns (if needed)
    # Or create new table: understat_xg_details

# 2. Update schema.py (add columns if needed)
# 3. Call from main.py orchestration
# 4. Re-run id_reconciliation to cross-link
```

### **Adding a New League**

Example: Add La Liga

```yaml
# config/leagues.yaml
leagues:
  SPAIN:
    id: ESP-La Liga
    seasons: ["2122", "2223", "2324", "2425"]
    exponent: 1.38  # Different from PL
    fbref_league_id: "La Liga"
```

```python
# main.py: Already multi-league aware
ingest_fbref(seasons, league='ESP-La Liga')

# ID mapping & features work automatically
# (master_id is universal across leagues)
```

---

## Performance Considerations

### **Indexing Strategy**

```sql
-- Key indexes for common queries
CREATE INDEX idx_match_results_date ON match_results(date);
CREATE INDEX idx_match_results_teams ON match_results(home_team_id, away_team_id);
CREATE INDEX idx_player_stats_season ON player_stats(season, league);
CREATE INDEX idx_injury_records_player ON injury_records(player_id, injury_date);
CREATE INDEX idx_id_mapping_entity ON id_mapping(entity_type, master_id);
```

**Query Cost** (typical):
- Get all matches for a team: **~5ms** (indexed by team_id)
- Build features for 380 matches: **~2s** (with warm cache)
- ID reconciliation (850 players): **~30s** (fuzzy matching)

### **Caching**

- FBref data cached in `.soccerdata/` (soccerdata library)
- Weather: Cache entire season in one API call
- Features: Rebuild only if new data ingested

---

## Error Handling & Recovery

### **Strategy: Fail Loud, Continue Smart**

```python
# ingest_fbref.py pattern
for season in seasons:
    try:
        data = fbref.read_schedule()
        insert_into_db(data)
    except Exception as e:
        logger.error(f"Season {season} failed: {e}")
        continue  # Try next season
        # (don't crash entire pipeline)
```

### **Rollback?**

SQLite doesn't support transactions well once committed, so:
- Each source is independent (no cross-table transactions)
- If ingest_fbref fails, all other sources still work
- Use `IF NOT EXISTS` and `INSERT OR IGNORE` for idempotency

---

## Testing Strategy

```
tests/
├── test_ingestion.py       # Mock FBref API calls, test parsing
├── test_schema.py          # Verify schema creation
├── test_id_reconciliation  # Fuzzy matching tests
├── test_feature_engineering # Feature building edge cases
└── test_metrics.py         # Pythagorean calculation, etc.
```

**Run tests:**
```bash
pytest tests/ -v
# or
python -m pytest tests/
```

---

## Deployment Scenarios

### **Local Development**
```bash
uv sync
python -m src.main --phase all
```

### **CI/CD (GitHub Actions)**
- Trigger: On push to main
- Step 1: Run tests
- Step 2: Run pipeline on subset (e.g., last 2 weeks)
- Step 3: Validate data quality
- Step 4: Commit training_features.csv to repo (for model training)

### **Docker Production**
```bash
docker build -t soccer-pred:latest .
docker run \
  -v /data:/data \
  -e DB_PATH=/data/sports_data.db \
  soccer-pred \
  python -m src.main --phase all
```

---

## Future Enhancements

1. **Multi-Source Conflicts**
   - What if FBref says 2 goals, Understat says 1.8 xG?
   - Decision: Trust xG from Understat, goals from FBref
   - Store both, flag conflicts

2. **Real-Time Updates**
   - Live betting odds integration
   - In-match probability updates
   - Streaming injury updates

3. **Graph Database**
   - Neo4j for player/team network (transfers, loans, coaching)
   - "Kevin De Bruyne played with X, who played with Y..."

4. **Temporal Analysis**
   - How did players' metrics change over career?
   - Formation evolution
   - Tactical shift detection

---

## Code Style & Conventions

- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Docstrings**: Google-style with type hints
- **Logging**: `logger.info()` for progress, `logger.warning()` for data issues, `logger.error()` for failures
- **SQL**: Use parameterized queries (prevent injection)
- **Comments**: High-level why, not low-level what

Example:
```python
def calculate_days_rest(conn: sqlite3.Connection, team_id: int, match_date: str) -> Optional[int]:
    """
    Calculate days rest since last match for a team.
    
    Used in fatigue scoring: fewer days = more tired.
    
    Args:
        conn: Database connection
        team_id: Team ID
        match_date: Current match date (YYYY-MM-DD)
    
    Returns:
        Number of days rest, or None if no prior matches
    """
    # Query for last match date
    recent_matches = get_team_matches_before_date(conn, team_id, match_date, limit=1)
    
    if len(recent_matches) == 0:
        return None  # No prior matches
    
    # Calculate gap
    last_match_date = pd.to_datetime(recent_matches.iloc[0]['date'])
    current_date = pd.to_datetime(match_date)
    return (current_date - last_match_date).days
```
