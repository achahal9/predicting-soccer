# BTTS & Double Chance Predictor Results

## Models Trained
- **BTTS** (Both Teams To Score): Binary classifier — will both teams score ≥1 goal?
- **1X** (Home Win or Draw): Binary classifier — will the home team avoid defeat?
- **X2** (Away Win or Draw): Binary classifier — will the away team avoid defeat?

Each trained with both Logistic Regression and Gradient Boosting (GBM).

## Test Set
- **Period**: 2024-01-01 onwards
- **Matches**: 2,647

## Summary

| Model | Accuracy | ROC-AUC | Brier Score |
| :--- | :--- | :--- | :--- |
| **BTTS / Logistic** | 53.87% | 0.5251 | 0.2474 |
| **BTTS / GBM** | 53.08% | 0.5234 | 0.2501 |
| **1X / Logistic** | 70.83% | **0.7408** | **0.1883** |
| **1X / GBM** | **71.51%** | 0.7328 | 0.1900 |
| **X2 / Logistic** | 67.02% | **0.7223** | **0.2091** |
| **X2 / GBM** | 66.75% | 0.7119 | 0.2123 |

## Key Findings

### Double Chance (1X / X2) — Strong
- **1X accuracy of ~71%** with ROC-AUC of 0.74 is a solid result.
- **X2 accuracy of ~67%** with ROC-AUC of 0.72 is also meaningful.
- Logistic Regression slightly outperforms GBM on AUC and calibration (Brier), suggesting the relationships are mostly linear.

### BTTS — Needs Work
- **~53-54% accuracy** is barely above the base rate (55.9% of test matches had BTTS).
- ROC-AUC of 0.52 indicates the current features provide almost no discriminative power for BTTS.
- **Recommendation**: BTTS likely requires different features — e.g., defensive strength metrics, clean sheet rates, xG data, or goalkeeper stats.

## Features Used
- Pythagorean Expectation (Home/Away)
- Elo Difference & Elo Win Probability
- Rolling 5-game averages: Goals, Shots, Shots on Target
- Recent form: Form3, Form5 (Home/Away)
