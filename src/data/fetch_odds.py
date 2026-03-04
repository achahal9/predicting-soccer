"""
Clean up fetch_odds.py: remove debug prints, add league name helper.
"""

import pandas as pd
import requests
import io

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"

LEAGUES = ["E0", "D1", "SP1", "I1", "F1"]

LEAGUE_NAMES = {
    "E0":  "Premier League",
    "D1":  "Bundesliga",
    "SP1": "La Liga",
    "I1":  "Serie A",
    "F1":  "Ligue 1",
}


def fetch_schedule_with_odds(leagues: list[str] | None = None) -> pd.DataFrame:
    """
    Fetch upcoming schedule and Bet365 odds from Football-Data.co.uk.

    Returns:
        DataFrame with columns:
        ['Div', 'LeagueName', 'Date', 'Time', 'HomeTeam', 'AwayTeam',
         'B365H', 'B365D', 'B365A']
        Sorted by Date then Time.
    """
    if leagues is None:
        leagues = LEAGUES

    try:
        response = requests.get(FIXTURES_URL, timeout=10)
        response.raise_for_status()

        csv_content = response.content.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(csv_content), on_bad_lines="skip")

        # Filter for requested leagues
        if "Div" in df.columns:
            df = df[df["Div"].isin(leagues)].copy()
        else:
            return pd.DataFrame()

        # Ensure Time column exists
        if "Time" not in df.columns:
            df["Time"] = "TBD"

        # Check odds columns
        for col in ["B365H", "B365D", "B365A"]:
            if col not in df.columns:
                df[col] = float("nan")

        cols = ["Div", "Date", "Time", "HomeTeam", "AwayTeam",
                "B365H", "B365D", "B365A"]
        df = df[[c for c in cols if c in df.columns]].copy()

        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df["LeagueName"] = df["Div"].map(LEAGUE_NAMES)
        df = df.sort_values(["Date", "Time"]).reset_index(drop=True)

        return df

    except Exception as e:
        print(f"[fetch_odds] Error: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_schedule_with_odds()
    print(df[["Div", "Date", "HomeTeam", "AwayTeam", "B365H", "B365D", "B365A"]].to_string())
