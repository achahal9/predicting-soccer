![CI Status](https://github.com/achahal9/predicting-soccer/actions/workflows/ci.yaml/badge.svg)

# Soccer Match & Player Performance Prediction

A comprehensive data engineering and machine learning system for predicting soccer match outcomes and player performance, built on FBref match data, weather conditions, injury reports, and advanced team/player metrics.

**Current Focus:** Premier League (2021-2026), with architecture designed for multi-league expansion.

---

## 🎯 Project Goals

- **Match Prediction**: Predict Premier League match outcomes (Win/Loss/Draw) using team form, player availability, and contextual features
- **Player Performance Metrics**: Analyze and predict individual player performance using historical stats and upcoming matchups
- **Comprehensive Data Integration**: Combine multiple data sources (match stats, injuries, weather, schedules, lineups)
- **Player Identity System**: Master database of player/team/referee IDs with cross-source mapping to track transfers and career history
- **Transfer Compatibility Analysis**: Assess how players would fit at different teams using positional, tactical, and personal compatibility metrics
- **Real-time Predictions**: Input upcoming lineups to generate match outcome probabilities

---

## 🏗️ System Architecture

### **Data Pipeline (Phase 1-3)**

```
FBref Match Data  ──┐
Player Stats      ──┤
Team Stats        ──┤
                     ├──→ Database Schema ──→ ID Reconciliation ──→ Feature Engineering
Injury Data       ──┤      (SQLite)          (Cross-Source)         (Training Data)
Weather Data      ──┤                                                
Schedule Metrics  ──┤
Lineups           ──┘
```

### **Database Schema**

- **Identity Tables**: `players`, `teams`, `managers`, `referees`
- **Cross-Source Mapping**: `id_mapping` (links FBref, Transfermarkt, external IDs to master records)
- **Match Data**: `match_results`, `match_env` (weather, venue), `match_lineups`
- **Performance**: `player_stats`, `team_stats` (season aggregates)
- **Career Tracking**: `transfers`, `team_rosters`, `team_managers`
- **Availability**: `injury_records`
- **Derived**: `schedule_metrics`, `training_features` (for ML)

---

## 📦 Installation & Setup

### **Prerequisites**
- Python 3.12+
- uv (fast package manager): `pip install uv`

### **Quick Start**

```bash
# Clone and navigate
git clone https://github.com/achahal9/predicting-soccer.git
cd predicting-soccer

# Install dependencies
uv sync

# Run full pipeline (data ingestion → feature engineering)
python -m src.main --phase all

# Or run specific phases
python -m src.main --phase ingest --seasons 2122 2223 2324 2425
python -m src.main --phase reconcile
python -m src.main --phase features
```

### **Via Docker**

```bash
docker build -t soccer-prediction .
docker run -v $(pwd):/app soccer-prediction python -m src.main --phase all
```

---

## 🔄 Pipeline Phases

### **Phase 0: Database Initialization**
Initializes SQLite schema with all tables and indexes.

### **Phase 1: Data Ingestion**
Pulls data from multiple sources:

- **FBref** (`ingest_fbref.py`): Match results, player/team stats
- **Injuries** (`ingest_injuries.py`): Player availability (Transfermarkt-based)
- **Weather** (`ingest_weather.py`): Open-Meteo API for historical/forecast data
- **Schedules** (`ingest_schedule.py`): Compute fatigue metrics (rest days, match density, travel distance)
- **Lineups** (`ingest_lineups.py`): Historical starting XIs and player ratings

### **Phase 2: ID Reconciliation** (`id_reconciliation.py`)
Cross-references players across data sources using:
- Name similarity matching (fuzzy)
- Birth date/position verification
- Confidence scoring
- Manual review flagging for uncertain matches

### **Phase 3: Feature Engineering** (`feature_engineering.py`)
Builds match-level features for ML:

**Team-level Features:**
- Recent form (last 5 matches: W/D/L, goals, xG)
- Season-to-date stats (goals, expected goals, possession)
- Pythagorean expectation (luck metric)

**Contextual Features:**
- Schedule fatigue (days rest, match density 14-day rolling)
- Travel distance from last match
- Injury impact score (missing key players)
- Squad quality (avg player rating, experience)
- Weather (temp, precipitation, wind, humidity)

**Output:** `training_features.csv` ready for model training

---

## 📊 Key Modules

### **Data Ingestion**

| Module | Source | Output | Status |
|--------|--------|--------|--------|
| `ingest_fbref.py` | FBref (soccerdata) | Matches, player/team stats | ✅ Complete |
| `ingest_injuries.py` | Transfermarkt | Injury records | 🚧 Template (needs scraper) |
| `ingest_weather.py` | Open-Meteo API | Weather for matches | ✅ Complete |
| `ingest_schedule.py` | Match calendar | Fatigue/travel metrics | ✅ Complete |
| `ingest_lineups.py` | FBref match reports | Historical lineups | 🚧 Template (needs parser) |

### **Processing**

| Module | Purpose |
|--------|---------|
| `schema.py` | 14-table SQLite schema |
| `id_reconciliation.py` | Fuzzy matching players across sources |
| `feature_engineering.py` | Build training features from raw data |
| `metrics.py` | Analytics (Pythagorean, home/away, H2H, consistency) |

### **Main Orchestration**

```bash
python -m src.main [--phase all|init|ingest|reconcile|features] [--seasons S1 S2...] [--verbose]
```

---

## 🛠️ Usage Examples

### **Run Complete Pipeline**
```bash
python -m src.main --phase all --seasons 2122 2223 2324 2425
```

### **Ingest Only**
```bash
python -m src.main --phase ingest --seasons 2425
```

### **Rebuild Features (after new data)**
```bash
python -m src.main --phase features
```

### **Programmatic Access**

```python
import sqlite3
from src.processing.feature_engineering import build_training_dataset
from src.processing.metrics import calculate_pythagorean_expectation, analyze_head_to_head

conn = sqlite3.connect('sports_data.db')

# Get training features
features_df = build_training_dataset(conn, season_filter='2425')

# Analyze team
xpect = calculate_pythagorean_expectation(goals_for=45, goals_against=30)  # 0.67
gap = xpect - 0.65  # Underperforming if actual win% = 0.65

# Head-to-head
h2h = analyze_head_to_head(conn, team1_id=1, team2_id=2, limit=10)
print(f"Team 1 record: {h2h['team1_wins']}-{h2h['team1_draws']}-{h2h['team1_losses']}")
```

### **Injury Impact**

```python
from src.data.ingest_injuries import get_team_injuries, calculate_injury_impact

injuries = get_team_injuries(conn, team_id=1, as_of_date='2025-02-11', status_filter='out')
impact = calculate_injury_impact(conn, team_id=1, as_of_date='2025-02-11')
print(f"Team has {impact['total_injured']} players out: {impact['out_players']}")
```

### **Schedule/Fatigue Metrics**

```python
from src.data.ingest_schedule import (
    calculate_days_rest, calculate_match_density, calculate_fatigue_score
)

rest = calculate_days_rest(conn, team_id=1, match_date='2025-02-15')
density = calculate_match_density(conn, team_id=1, match_date='2025-02-15')
fatigue = calculate_fatigue_score(conn, team_id=1, match_date='2025-02-15')
print(f"Team A: {rest} days rest, {density} matches in 14d, fatigue={fatigue:.2f}")
```

---

## 📈 Next Steps (Phase 4-5)

### **Phase 4: Model Training & Evaluation**
- [ ] Build classification model (Logistic Regression, Random Forest, XGBoost)
- [ ] Train on 2021-2024, validate on 2024-2025
- [ ] Cross-validation and hyperparameter tuning
- [ ] Feature importance analysis (SHAP)
- [ ] Compare vs. Pythagorean expectation baseline

**See**: `notebooks/` for exploratory analysis

### **Phase 5: Real-Time Inference**
- [ ] Web API for match predictions (Flask/FastAPI)
- [ ] Lineup input interface
- [ ] Real-time feature fetching
- [ ] Prediction confidence scores
- [ ] Model explainability (why this prediction?)

---

## 🎯 MVP Scope

**Completed:**
- Multi-source data ingestion (FBref, weather, schedule)
- Comprehensive schema with ID mapping
- Feature engineering pipeline
- Pythagorean expectation analysis

**In Progress:**
- Injury data integration (needs web scraper)
- Historical lineups (partial)

**Not Yet Started:**
- Classification models
- Real-time prediction endpoint
- Transfer compatibility analysis

---

## 📋 Configuration

### **Leagues** (`config/leagues.yaml`)
Currently configured for Premier League only. To add other leagues:

```yaml
leagues:
  ENGLAND:
    id: ENG-Premier League
    seasons: ["2122", "2223", "2324", "2425"]
    exponent: 1.35  # Pythagorean exponent
  SPAIN:
    id: ESP-La Liga
    seasons: ["2122", "2223", "2324", "2425"]
    exponent: 1.35
```

### **Data Sources** (in module files)
- **FBref**: soccerdata library (free)
- **Weather**: Open-Meteo API (free, no key)
- **Injuries**: Transfermarkt (needs scraper)
- **Lineups**: FBref (via soccerdata)

---

## 🔒 Data Quality & Validation

- Schema enforces referential integrity (foreign keys)
- ID mapping tracks confidence scores (0-1)
- Manual review flagged for matches < 0.95 confidence
- Missing data handling:
  - NULL for incomplete matches
  - Imputation in feature engineering
  - Logging of missing sources

**Check data quality:**
```python
from src.database.id_reconciliation import audit_id_mappings

audit = audit_id_mappings(conn)
print(f"Player coverage: {audit['coverage_percent']}% ({audit['mapped_players']}/{audit['total_players']})")
```

---

## 🐛 Troubleshooting

**Issue**: `soccerdata` scraping fails
- FBref sometimes blocks requests. Try:
  - Clear cache: `rm -rf .soccerdata`
  - Add delays between requests in `ingest_fbref.py`
  - Check your IP isn't rate-limited

**Issue**: Weather data missing
- Open-Meteo archive only has historical data. For future dates, use forecast endpoint.

**Issue**: Player names don't match across sources
- Run ID reconciliation with lower confidence threshold: `reconcile_players_across_sources(conn, auto_merge_threshold=0.80)`

---

## 📚 Additional Resources

- **FBref Data**: https://fbref.com/en/comps/9/Premier-League-Stats
- **Open-Meteo**: https://open-meteo.com/#api-documentation
- **Soccerdata Docs**: https://github.com/rcnelson/soccerdata

---

## 📝 License

MIT

---

## 👤 Author

Built by [@achahal9](https://github.com/achahal9)

---

## 🚀 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes and push
4. Open a pull request

Priority areas:
- [ ] Injury data scraper (Transfermarkt)
- [ ] Lineup parser improvements
- [ ] Transfer data integration
- [ ] Model training notebooks
- [ ] Real-time prediction API