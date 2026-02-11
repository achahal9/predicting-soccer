# Quick Start Guide

Get the soccer prediction system up and running in 5 minutes.

---

## 🚀 Installation (2 minutes)

### **Via VS Code DevContainer (Recommended)**

1. Open workspace in VS Code
2. When prompted: "Reopen in DevContainer"
3. Container auto-installs Python 3.12 + dependencies
4. Ready to go!

### **Via Local Python**

```bash
# Prerequisites: Python 3.12+, uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repo
git clone https://github.com/achahal9/predicting-soccer.git
cd predicting-soccer

# Install dependencies
uv sync

# Verify installation
python -c "import sqlite3; import soccerdata; import pandas; print('✓ All dependencies installed')"
```

---

## ⚡ Run the Pipeline (3 minutes)

### **Option 1: Full Pipeline (Easiest)**

```bash
# Run everything: data ingestion → feature engineering
python -m src.main --phase all

# Output:
# ✓ Database schema initialized
# ✓ FBref data ingested (matches, player stats)
# ✓ Weather data ingested
# ✓ Schedule metrics computed
# ✓ ID reconciliation complete (96.6% coverage)
# ✓ Training features built (380 matches x 34 features)
# → training_features.csv ready for model training
```

### **Option 2: Specific Phases**

```bash
# Just ingest data
python -m src.main --phase ingest --seasons 2122 2223 2324 2425

# Just reconcile IDs across sources
python -m src.main --phase reconcile

# Just build features
python -m src.main --phase features
```

### **Option 3: Custom Seasons**

```bash
# Only ingest recent 2 seasons
python -m src.main --phase ingest --seasons 2324 2425
```

---

## 📊 Explore the Data

### **In Python**

```python
import sqlite3
import pandas as pd
from src.processing.feature_engineering import build_training_dataset
from src.processing.metrics import analyze_head_to_head

# Connect to database
conn = sqlite3.connect('sports_data.db')

# 1. Load training features
features = build_training_dataset(conn)
print(f"Shape: {features.shape}")  # (380, 34)
print(f"Columns: {list(features.columns)}")
features.head()

# 2. Browse matches
matches = pd.read_sql_query(
    "SELECT m.date, ht.team_name, at.team_name, m.home_goals, m.away_goals "
    "FROM match_results m "
    "JOIN teams ht ON m.home_team_id = ht.team_id "
    "JOIN teams at ON m.away_team_id = at.team_id "
    "ORDER BY m.date DESC LIMIT 10",
    conn
)
print(matches)

# 3. Check injury data
injuries = pd.read_sql_query(
    "SELECT COUNT(*) as total_injuries FROM injury_records",
    conn
)
print(f"Total injury records: {injuries.iloc[0]['total_injuries']}")

# 4. Analyze a team (e.g., Manchester City)
conn.execute("SELECT team_id FROM teams WHERE team_name = 'Manchester City'")
city_id = conn.execute("SELECT team_id FROM teams WHERE team_name = 'Manchester City'").fetchone()[0]

h2h = analyze_head_to_head(conn, city_id, city_id + 1, limit=5)
print(f"Manchester City vs. Liverpool (last 5):")
print(f"  City: {h2h['team1_wins']}-{h2h['team1_draws']}-{h2h['team1_losses']}")

conn.close()
```

### **In Notebook**

See [notebooks/notebook.ipynb](notebooks/notebook.ipynb) for interactive examples:
- Explore feature distributions
- Visualize team form trends
- Compare Pythagorean expectation vs. actual results

---

## 🔍 Common Tasks

### **Task 1: Check Data Quality**

```python
from src.database.id_reconciliation import audit_id_mappings

audit = audit_id_mappings(conn)
print(f"Player data coverage: {audit['coverage_percent']}%")
#  Output: Player data coverage: 96.6%
```

### **Task 2: Calculate Team Fatigue**

```python
from src.data.ingest_schedule import calculate_fatigue_score

fatigue = calculate_fatigue_score(conn, team_id=1, match_date='2025-02-15')
print(f"Team fatigue score: {fatigue:.2f}")  # 0.0 = fresh, 1.0 = exhausted
# Output: Team fatigue score: 0.45
```

### **Task 3: Get Match Weather**

```python
from src.data.ingest_weather import get_match_weather

weather = get_match_weather(conn, match_id='match_123')
print(f"Temp: {weather['temperature_celsius']:.1f}°C, "
      f"Rain: {weather['precipitation_mm']:.1f}mm, "
      f"Wind: {weather['wind_speed_kmh']:.1f} km/h")
```

### **Task 4: Analyze Team Injuries**

```python
from src.data.ingest_injuries import get_team_injuries, calculate_injury_impact

# See who's out
injuries = get_team_injuries(conn, team_id=1, status_filter='out')
print(f"Players out: {', '.join(injuries['full_name'].tolist())}")

# Get impact score
impact = calculate_injury_impact(conn, team_id=1, as_of_date='2025-02-15')
print(f"Missing {impact['total_injured']} players (impact: {impact['impact_score']:.1%})")
```

### **Task 5: Compare Teams (H2H)**

```python
from src.processing.metrics import analyze_head_to_head

# Get Manchester City and Liverpool IDs
teams = pd.read_sql_query("SELECT team_id, team_name FROM teams", conn)
city_id = teams[teams['team_name'] == 'Manchester City'].iloc[0]['team_id']
liv_id = teams[teams['team_name'] == 'Liverpool'].iloc[0]['team_id']

h2h = analyze_head_to_head(conn, city_id, liv_id, limit=10)
print(f"Manchester City vs Liverpool (last 10):")
print(f"  Record: {h2h['team1_wins']}W-{h2h['team1_draws']}D-{h2h['team1_losses']}L")
print(f"  Goal difference: {h2h['team1_goal_diff']}")
print(f"  Avg goals/match: {h2h['avg_goals_per_match']}")
```

---

## 📁 File Structure

```
predicting-soccer/
├── src/
│   ├── main.py                          ← Run this
│   ├── data/
│   │   ├── ingest_fbref.py              ← Match/player/team stats
│   │   ├── ingest_injuries.py           ← Availability
│   │   ├── ingest_weather.py            ← Climate data
│   │   ├── ingest_schedule.py           ← Fatigue metrics
│   │   └── ingest_lineups.py            ← Starting XIs
│   ├── database/
│   │   ├── schema.py                    ← Database design
│   │   └── id_reconciliation.py         ← Cross-source matching
│   └── processing/
│       ├── metrics.py                   ← Analytics
│       └── feature_engineering.py       ← ML features
├── config/
│   └── leagues.yaml                     ← League config
├── notebooks/
│   └── notebook.ipynb                   ← Exploratory analysis
├── tests/
│   └── test_placeholder.py
├── ARCHITECTURE.md                      ← Design docs (READ THIS!)
├── README.md                            ← Overview
├── pyproject.toml                       ← Dependencies
├── sports_data.db                       ← SQLite database (auto-created)
└── training_features.csv                ← ML data (auto-created)
```

---

## 🐛 Troubleshooting

### **Problem: `uv sync` fails to install soccerdata**
```bash
# Solution: soccerdata may need build tools
python -m pip install --upgrade pip setuptools wheel
uv sync
```

### **Problem: FBref scraping times out**
```bash
# Solution: Clear cache and retry with delays
rm -rf .soccerdata
python -m src.main --phase ingest  # Will retry automatically
```

### **Problem: Database locked or corrupted**
```bash
# Solution: Delete and rebuild
rm sports_data.db
python -m src.main --phase all
```

### **Problem: "No matches found" in features**
```bash
# Solution: Ensure ingestion completed successfully
python -c "import sqlite3; conn = sqlite3.connect('sports_data.db'); \
  matches = conn.execute('SELECT COUNT(*) FROM match_results').fetchone()[0]; \
  print(f'Matches in DB: {matches}')"
# Should show > 0
```

---

## 📚 Next Steps

1. **Explore data** → Open `notebooks/notebook.ipynb` and run cells
2. **Train a model** → See `MODELING.md` (coming soon)
3. **Deploy prediction API** → See `DEPLOYMENT.md` (coming soon)
4. **Add a new data source** → See `ARCHITECTURE.md` → Extensibility Points

---

## ⏱️ Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| `uv sync` | 30s | One-time install |
| Full pipeline | 3-5 min | Depends on internet (FBref scraping) |
| Data ingestion only | 2-3 min | No feature engineering |
| Feature engineering | 30s | From existing database |
| ID reconciliation | 1 min | Fuzzy matching 800+ players |

---

## 🆘 Getting Help

- **Code errors?** Check logs: most functions use `logger.info()` / `logger.warning()`
- **Data questions?** See [ARCHITECTURE.md](ARCHITECTURE.md) → Database Schema
- **Features unclear?** See [README.md](README.md) → Usage Examples
- **Bug?** Open an issue on GitHub

---

## ✨ You're Ready!

Your system is now:
- ✅ Collecting Premier League match data
- ✅ Tracking player availability (injuries)
- ✅ Capturing weather conditions
- ✅ Computing schedule fatigue metrics
- ✅ Building ML-ready features

**Next:** Train a model on `training_features.csv` 🚀
