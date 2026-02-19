# 2026 Season Data Checklist

To ensure the `predicting-soccer` repository remains up-to-date for the 2026 season and beyond, follow this checklist.

## Data Sources

### 1. Match Results & Statistics
*   **Source**: [Football-Data.co.uk](https://www.football-data.co.uk/data.php)
*   **Leagues**:
    *   Premier League: `E0.csv`
    *   Bundesliga: `D1.csv`
    *   La Liga: `SP1.csv`
    *   Serie A: `I1.csv`
    *   Ligue 1: `F1.csv`
*   **Update Frequency**: Weekly (usually Monday/Tuesday after weekend games).

### 2. Elo Ratings
*   **Source**: [ClubElo.com](http://api.clubelo.com/Height) (API) or main site.
*   **Format**: CSV / API JSON.
*   **Update Frequency**: After every match (continuous).

## Maintenance Procedures

### A. Automatic Updates (Recommended)
The repository includes a GitHub Action (`.github/workflows/weekly_data_update.yml`) that runs weekly.
1.  Check the **Actions** tab in GitHub to ensure the workflow is succeeding.
2.  If the workflow indicates "New Data Found" and commits changes, pull the latest changes to your local environment:
    ```bash
    git pull origin main
    ```

### B. Manual Updates
If automation fails or manual intervention is needed:
1.  **Download** the latest CSVs for the 5 leagues from Football-Data.co.uk.
2.  **Save/Replace** these files in the `src/data/historicaldata2000-25/` directory.
3.  **Run** the ingest/update script locally (if you want to append to the master `Matches.csv`):
    ```bash
    python src/data/update_pipeline.py --manual
    ```
3.  **Verify** the new rows in `src/data/historicaldata2000-25/Matches.csv`.
4.  **Commit** and push the updated CSV.

## Data Quality Checks
*   [ ] **Missing Values**: Check for missing `FTResult` or odds.
*   [ ] **Team Name Mapping**: Ensure new teams (promoted teams) are mapped correctly if names differ between data sources (e.g., "Man United" vs "Manchester United").
*   [ ] **Date Format**: Ensure `Date` is consistently `YYYY-MM-DD`.
