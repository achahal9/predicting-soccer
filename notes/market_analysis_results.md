# Market Analysis Results

## Overview
Backtest of the Phase 2 model (Elo + Lagged Stats + Pythagorean) against historical Bet365 closing odds for matches from 2024 onwards.

- **Model Accuracy**: 52.06%
- **Matches with Bet365 Odds**: 2,647
- **Avg Bookmaker Margin**: 4.66%

## Value Bet Backtest (Flat Stake = 1 Unit)

| EV Threshold | Total Bets | Win Rate | Avg Odds | Avg EV | Profit | ROI |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ≥ 5% | 1,910 | 27.4% | 3.98 | 16.2% | -232.41 | **-12.17%** |
| ≥ 10% | 1,175 | 24.7% | 4.29 | 21.7% | -192.84 | **-16.41%** |
| ≥ 15% | 714 | 21.6% | 4.74 | 27.8% | -134.67 | **-18.86%** |

## League Breakdown (EV ≥ 5%)

| League | Bets | Win Rate | ROI |
| :--- | :--- | :--- | :--- |
| Premier League | 463 | 24.4% | -12.7% |
| Bundesliga | 357 | 25.8% | **-6.2%** |
| La Liga | 375 | 29.9% | -14.0% |
| Serie A | 386 | 28.5% | -20.6% |
| Ligue 1 | 329 | 29.5% | **-5.9%** |

## Key Takeaways

1. **Model overestimates underdog probabilities**: The model predicts higher-than-actual probabilities for outcomes with higher odds (underdogs/draws), resulting in many false "value" signals.
2. **Probability calibration needed**: While the model predicts the *correct winner* 52% of the time, its *probability estimates* are not well-calibrated — it needs Platt scaling or isotonic regression.
3. **Bundesliga & Ligue 1 show promise**: The least negative ROI leagues, suggesting the model performs relatively better in these markets.
4. **Bookmaker efficiency is real**: The 4.7% margin means we need a significant edge (>5%) just to break even.

## Recommendations
- Apply **probability calibration** (CalibratedClassifierCV) before using probabilities for value betting.
- Focus on **selective betting** — only bet when model confidence is very high AND EV is substantial.
- Consider **draw exclusion** — draws are hardest to predict and inflate false value signals.
- Explore **closing line value** (CLV) as a better metric than raw EV.
