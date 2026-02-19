# Model Verification Results

## Summary
Successful systematic improvement of the predictive model through two phases of feature engineering.

## Results Table

| Model | Accuracy | Improvement | Key Features |
| :--- | :--- | :--- | :--- |
| **Baseline (Win %)** | 41.53% | - | Historical Win Rates |
| **Pythagorean Exp.** | 50.09% | +8.56% | Expected Goals (GF/GA) |
| **Phase 2 (Elo + Lagged)** | **52.06%** | **+1.97%** | Elo Diff, Rolling Stats |

## Feature Importance (Phase 2)
The `EloDifference` feature proved to be the most significant predictor, followed by `EloProbHome` and `AwayShotsAvg`.

1.  **EloDifference** (0.4387)
2.  **EloProbHome** (0.1748)
3.  **AwayShotsAvg** (0.0519)
4.  **PythagoreanAway** (0.0398)

## Conclusion
Integrating Elo ratings and recent match statistics (rolling 5-game averages) provides a robust signal for predicting match outcomes, significantly outperforming simple historical baselines.
