# Features Reference Guide

Complete documentation of all features in the training dataset.

---

## Overview

**Total Features**: ~34 dimensions per match
**Output Format**: `training_features.csv` (N_matches × 34 columns)
**Target Variable**: `outcome` (home_win, draw, away_win)

---

## Feature Categories

### **1. Match Metadata** (3 features)

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `match_id` | string | — | Unique match identifier |
| `date` | datetime | 2021-2026 | Match date |
| `season` | string | 2122-2425 | Season code (e.g., "2425" = 2024-2025) |

---

### **2. Home Team Form** (7 features)

*Based on last 5 matches played by home team*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `home_wins` | int | 0-5 | Wins in last 5 matches |
| `home_draws` | int | 0-5 | Draws in last 5 matches |
| `home_losses` | int | 0-5 | Losses in last 5 matches |
| `home_goals_for` | int | 0-20 | Goals scored in last 5 matches |
| `home_goals_against` | int | 0-20 | Goals conceded in last 5 matches |
| `home_win_pct` | float | 0.0-1.0 | Win percentage (0.0 = 0%, 1.0 = 100%) |
| `home_points_per_game` | float | 0.0-3.0 | Avg points per match (0 = 0pts, 3 = 3pts/win) |

**Interpretation**: Higher `win_pct` and `points_per_game` = Hot form

---

### **3. Home Team Season Stats** (8 features)

*Cumulative statistics for season (up to current match)*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `home_wins_season` | int | 0-30 | Season wins |
| `home_draws_season` | int | 0-15 | Season draws |
| `home_losses_season` | int | 0-15 | Season losses |
| `home_gf_season` | int | 0-100 | Season goals for |
| `home_ga_season` | int | 0-100 | Season goals against |
| `home_xg_season` | float | 0-80 | Sum of expected goals (xG) |
| `home_xga_season` | float | 0-80 | Sum of expected goals against (xGA) |
| `home_possession_avg` | float | 40-60 | Avg possession % |

**Derived Metric**: Pythagorean expectation = $\frac{xG^{1.35}}{xG^{1.35} + xGA^{1.35}}$

---

### **4. Home Team Injury Impact** (2 features)

*Player availability status*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `home_injury_count` | int | 0-11 | Number of players out/doubtful |
| `home_injury_impact_score` | float | 0.0-1.0 | Normalized impact (0 = no injuries, 1 = all 11 out) |

**Calculation**: `impact = min(injured_count / 11.0, 1.0)`

**Example**: 3 players out → impact = 0.27

---

### **5. Home Team Squad Quality** (2 features)

*Average player attributes from starting XI or season stats*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `home_squad_avg_rating` | float | 6.0-8.0 | Avg player rating from match lineups (if available) |
| `home_squad_avg_apps` | int | 10-35 | Avg appearances (experience level) |

**Data Source**: Match lineups or season player_stats table

**Interpretation**: Higher rating / more apps = stronger squad quality

---

### **6. Home Team Schedule Health** (4 features)

*Fatigue and congestion metrics*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `home_days_rest` | int | 3-20 | Days since last match |
| `home_match_density` | int | 0-5 | Matches in last 14 days |
| `home_fatigue_score` | float | 0.0-1.0 | Composite fatigue (0=fresh, 1=exhausted) |
| `home_goal_diff` | int | -15-15 | Goals for - goals against (last 5 matches) |

**Fatigue Formula**:
$$\text{fatigue} = 0.5 \times (1 - \frac{\text{rest}}{7}) + 0.3 \times \min(\frac{\text{matches}}{5}, 1) + 0.2 \times \min(\frac{\text{away\\_streak}}{3}, 1)$$

**Examples**:
- 3 days rest + 3 matches in 14d + 1 away = 0.65 (moderately tired)
- 10 days rest + 1 match in 14d + 0 away = 0.15 (very fresh)

---

### **7. Away Team Features** (Same as Home, minus one)

*Identical structure to Home features, with three exceptions:*

| Feature | Differs From Home? | Notes |
|---------|-------------------|-------|
| `away_wins`, `away_losses`, etc. | No | Same 7 form features |
| `away_wins_season`, etc. | No | Same 8 season features |
| `away_injury_count`, etc. | No | Same 2 injury features |
| `away_squad_avg_rating`, etc. | No | Same 2 quality features |
| `away_days_rest`, `away_fatigue_score`, etc. | No | Same 4 schedule features |
| `away_travel_km` | **YES** | Extra: distance traveled from last match |

---

### **8. Away-Specific Feature** (1 feature)

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `away_travel_km` | float | 0-400 | Travel distance to home team's stadium |

**Calculation**: Haversine distance between stadiums (great-circle distance)

**Example**: Liverpool → Manchester City ≈ 35 km, Newcastle → Southampton ≈ 300 km

---

### **9. Contextual Features** (4 features)

*Environmental conditions at match*

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `temp_celsius` | float | 0-25 | Temperature at kickoff |
| `precipitation_mm` | float | 0-20 | Rainfall in 24h before match |
| `wind_speed_kmh` | float | 0-30 | Average wind speed |
| `humidity_percent` | float | 30-100 | Relative humidity |

**Data Source**: Open-Meteo historical API

**Impact**: Extreme weather (rain, cold) may favor defensive play; wind affects long balls

---

### **10. Target Variable** (1 feature)

| Feature | Type | Values | Notes |
|---------|------|--------|-------|
| `outcome` | categorical | home_win, draw, away_win | Only present for completed matches |

**Encoding for ML**:
- One-hot: `[home_win, draw, away_win]` ∈ {0,1}³
- Label: `[0, 1, 2]`

---

## Feature Summary Table

```
TOTAL FEATURES: 34

Metadata:           3
Home Form:          7
Home Season:        8
Home Injury:        2
Home Quality:       2
Home Schedule:      4
Away Form:          7
Away Season:        8
Away Injury:        2
Away Quality:       2
Away Schedule:      5 (includes travel)
Contextual:         4
Target:             1
```

---

## Data Quality & Missingness

### **Expected Missing Values**

| Feature | % Missing | Reason | Handling |
|---------|-----------|--------|----------|
| Squad rating | 5-10% | Lineups not scraped | Use season average as fallback |
| Travel distance | <1% | Team not in PL venues | Set to 0 |
| Weather | 1-3% | API fails for old dates | Linear interpolation with neighbors |
| Injury counts | 0% | Template ingester | All initialized to 0 |
| Form/Season stats | 0% | Always computed | None |

### **Imputation Strategy**

```python
# In feature_engineering.py
if pd.isna(df['home_squad_avg_rating']):
    df['home_squad_avg_rating'] = df['home_squad_avg_apps'] * 0.15 + 6.0  # Rough estimate

df['precipitation_mm'] = df['precipitation_mm'].fillna(0)  # No rain assumed
df['away_travel_km'] = df['away_travel_km'].fillna(150)  # Average travel
```

---

## Example Feature Vector

**Match**: Manchester City (H) vs. Liverpool (A), 2025-02-15

```python
{
    'match_id': 'mc_liv_20250215',
    'date': '2025-02-15',
    'season': '2425',
    
    # Man City form (last 5: WWDLW)
    'home_wins': 3,
    'home_draws': 1,
    'home_losses': 1,
    'home_goals_for': 12,
    'home_goals_against': 4,
    'home_win_pct': 0.6,
    'home_points_per_game': 2.4,
    
    # Man City season
    'home_wins_season': 16,
    'home_draws_season': 2,
    'home_losses_season': 2,
    'home_gf_season': 52,
    'home_ga_season': 20,
    'home_xg_season': 48.5,
    'home_xga_season': 19.2,
    'home_possession_avg': 63.5,
    
    # Man City injuries
    'home_injury_count': 1,  # De Bruyne doubtful
    'home_injury_impact_score': 0.09,
    
    # Man City quality
    'home_squad_avg_rating': 7.8,
    'home_squad_avg_apps': 28,
    
    # Man City schedule
    'home_days_rest': 4,
    'home_match_density': 3,
    'home_fatigue_score': 0.32,
    'home_goal_diff': 8,
    
    # Liverpool (away)
    'away_wins': 2,
    'away_draws': 1,
    'away_losses': 2,
    'away_goals_for': 9,
    'away_goals_against': 7,
    'away_win_pct': 0.4,
    'away_points_per_game': 1.4,
    
    'away_wins_season': 14,
    'away_draws_season': 1,
    'away_losses_season': 4,
    'away_gf_season': 48,
    'away_ga_season': 24,
    'away_xg_season': 46.2,
    'away_xga_season': 23.1,
    'away_possession_avg': 58.0,
    
    'away_injury_count': 0,
    'away_injury_impact_score': 0.0,
    'away_squad_avg_rating': 7.6,
    'away_squad_avg_apps': 26,
    
    'away_days_rest': 3,
    'away_match_density': 4,
    'away_fatigue_score': 0.42,
    'away_goal_diff': 2,
    'away_travel_km': 35,  # Short trip
    
    # Environment
    'temp_celsius': 8.5,
    'precipitation_mm': 2.1,
    'wind_speed_kmh': 15.0,
    'humidity_percent': 72,
    
    # Target (if match played)
    'outcome': 'home_win'  # Man City won 2-1
}
```

---

## Feature Engineering Notebook

See [notebooks/feature_exploration.ipynb](notebooks/feature_exploration.ipynb) (coming soon) for:
- Feature distribution plots
- Correlation matrix (which features matter?)
- Missing data patterns
- Outlier detection
- Feature importance from base model

---

## Using Features in ML

### **Load & Preprocess**

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Load features
df = pd.read_csv('training_features.csv')

# Drop non-feature columns
X = df.drop(['outcome', 'match_id', 'date', 'season'], axis=1)
y = df['outcome']  # home_win=0, draw=1, away_win=2

# Encode target
y_encoded = (y == 'home_win').astype(int)  # Binary: home win or not

# Handle missing values (minimal, but just in case)
X = X.fillna(X.mean())

# Scale features (important for linear models)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train/test split (temporal)
train_size = int(0.8 * len(X))
X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
y_train, y_test = y_encoded[:train_size], y_encoded[train_size:]

# Train model
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)
print(f"Accuracy: {model.score(X_test, y_test):.2%}")
```

---

## Feature Correlations (Expected)

```
Positively correlated with home win:
  • home_win_pct (recent form)
  • home_xg_season (attacking threat)
  • away_fatigue_score (opponent tired)
  • home_days_rest (team fresh)

Negatively correlated with home win:
  • away_goals_for (opponent strength)
  • home_injury_impact_score (missing players)
  • away_travel_km (opponent not traveling far)
```

---

## Seasonal Patterns (Hypothesis)

*Features may vary by season phase:*

| Phase | Duration | Notes |
|-------|----------|-------|
| Opening | Aug-Sep | Low fatigue, fresh lineups |
| Autumn | Oct-Nov | Consistent fatigue, injury accumulation starts |
| Winter | Dec-Feb | Max fatigue (congestion), weather impacts |
| Spring | Mar-May | Decreasing fatigue, injury recovery |

Consider seasonal dummy variables if needed.

---

## Next: Model Training

See **[MODELING.md](MODELING.md)** (coming soon) for:
- Baseline models (Logistic Regression, Pythagorean baseline)
- Advanced models (XGBoost, LightGBM)
- Cross-validation strategies
- Hyperparameter tuning
- Model evaluation (AUC, precision, recall)

---

## Questions?

- **Feature X seems off?** Check [ARCHITECTURE.md](ARCHITECTURE.md) → Database Schema for data sources
- **How is feature Y calculated?** See [src/processing/feature_engineering.py](src/processing/feature_engineering.py) code
- **Missing feature Z?** Raise an issue or add it following the pattern
