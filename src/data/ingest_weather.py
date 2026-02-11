"""
Weather data ingestion module.

Sources:
- Open-Meteo API (free, no authentication required): https://open-meteo.com/
- Provides: temperature, precipitation, wind speed, humidity for match venues

This module fetches historical and forecasted weather data for Premier League venues.
"""

import sqlite3
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Premier League stadium coordinates (latitude, longitude)
PL_VENUES = {
    'Arsenal': (51.555, -0.108),
    'Aston Villa': (52.509, -1.884),
    'Bournemouth': (50.735, -1.838),
    'Brentford': (51.491, -0.294),
    'Brighton': (50.861, -0.083),
    'Chelsea': (51.482, -0.191),
    'Crystal Palace': (51.398, -0.085),
    'Everton': (53.439, -2.966),
    'Fulham': (51.475, -0.222),
    'Ipswich Town': (52.054, 1.145),
    'Leicester City': (52.620, -1.142),
    'Liverpool': (53.431, -2.961),
    'Manchester City': (53.483, -2.200),
    'Manchester United': (53.463, -2.291),
    'Newcastle United': (54.975, -1.622),
    'Nottingham Forest': (52.940, -1.133),
    'Southampton': (50.906, -1.391),
    'Tottenham': (51.604, -0.066),
    'West Ham': (51.539, 0.016),
    'Wolverhampton': (52.510, -2.130),
}

def get_venue_coords(team_name: str) -> Optional[Tuple[float, float]]:
    """Get latitude/longitude for a team's home stadium."""
    return PL_VENUES.get(team_name)

def fetch_historical_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Fetch historical weather data from Open-Meteo for a location.
    
    Args:
        latitude: Stadium latitude
        longitude: Stadium longitude
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with datetime, temperature, precipitation, wind_speed, humidity
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'start_date': start_date,
        'end_date': end_date,
        'hourly': ['temperature_2m', 'precipitation', 'windspeed_10m', 'relative_humidity_2m'],
        'temperature_unit': 'celsius',
        'windspeed_unit': 'kmh',
        'precipitation_unit': 'mm',
        'timezone': 'Europe/London'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Aggregate hourly data to daily
        df = pd.DataFrame({
            'datetime': pd.to_datetime(data['hourly']['time']),
            'temp': data['hourly']['temperature_2m'],
            'precip': data['hourly']['precipitation'],
            'windspeed': data['hourly']['windspeed_10m'],
            'humidity': data['hourly']['relative_humidity_2m']
        })
        
        df['date'] = df['datetime'].dt.date
        daily = df.groupby('date').agg({
            'temp': 'mean',
            'precip': 'sum',
            'windspeed': 'mean',
            'humidity': 'mean'
        }).reset_index()
        
        return daily
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return pd.DataFrame()

def fetch_forecast_weather(
    latitude: float,
    longitude: float,
    forecast_days: int = 7
) -> pd.DataFrame:
    """
    Fetch weather forecast from Open-Meteo.
    
    Args:
        latitude: Stadium latitude
        longitude: Stadium longitude
        forecast_days: Number of days to forecast (default 7)
    
    Returns:
        DataFrame with forecast data
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'daily': ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum', 'windspeed_10m_max'],
        'temperature_unit': 'celsius',
        'windspeed_unit': 'kmh',
        'precipitation_unit': 'mm',
        'forecast_days': forecast_days,
        'timezone': 'Europe/London'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame({
            'date': pd.to_datetime(data['daily']['time']).date,
            'temp_max': data['daily']['temperature_2m_max'],
            'temp_min': data['daily']['temperature_2m_min'],
            'precip': data['daily']['precipitation_sum'],
            'windspeed': data['daily']['windspeed_10m_max']
        })
        
        return df
    except Exception as e:
        logger.error(f"Error fetching forecast: {e}")
        return pd.DataFrame()

def ingest_match_weather(
    conn: sqlite3.Connection,
    match_id: str,
    team_name: str,
    match_date: str
):
    """
    Ingest weather data for a specific match.
    
    Args:
        conn: Database connection
        match_id: Match ID
        team_name: Home team name (to get venue)
        match_date: Match date (YYYY-MM-DD)
    """
    coords = get_venue_coords(team_name)
    if not coords:
        logger.warning(f"No coordinates found for {team_name}")
        return
    
    lat, lon = coords
    
    # Fetch weather for match date
    weather_data = fetch_historical_weather(lat, lon, match_date, match_date)
    
    if len(weather_data) == 0:
        logger.warning(f"No weather data for {team_name} on {match_date}")
        return
    
    row = weather_data.iloc[0]
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO match_env
        (match_id, temp_celsius, precipitation_mm, wind_speed_kmh, humidity_percent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (match_id, row['temp'], row['precip'], row['windspeed'], row['humidity'], datetime.now()))
    conn.commit()
    logger.info(f"Weather data ingested for match {match_id}: {row['temp']:.1f}°C, {row['precip']:.1f}mm")

def ingest_historical_weather(
    conn: sqlite3.Connection,
    start_date: str = '2021-01-01',
    end_date: str = None
):
    """
    Ingest historical weather for all Premier League matches.
    
    Args:
        conn: Database connection
        start_date: Season start (YYYY-MM-DD)
        end_date: Season end (YYYY-MM-DD), default to today
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"Ingesting historical weather from {start_date} to {end_date}...")
    
    # Get all matches that need weather data
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.match_id, tm.team_name, m.date
        FROM match_results m
        JOIN teams tm ON m.home_team_id = tm.team_id
        LEFT JOIN match_env me ON m.match_id = me.match_id
        WHERE me.match_env_id IS NULL
        AND m.date BETWEEN ? AND ?
        ORDER BY m.date
    ''', (start_date, end_date))
    
    matches_to_update = cursor.fetchall()
    logger.info(f"Found {len(matches_to_update)} matches needing weather data")
    
    for match_id, team_name, match_date in matches_to_update:
        ingest_match_weather(conn, match_id, team_name, match_date)

def get_match_weather(conn: sqlite3.Connection, match_id: str) -> Optional[Dict]:
    """Get weather data for a specific match."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT temp_celsius, precipitation_mm, wind_speed_kmh, humidity_percent
        FROM match_env
        WHERE match_id = ?
    ''', (match_id,))
    
    result = cursor.fetchone()
    if result:
        return {
            'temperature_celsius': result[0],
            'precipitation_mm': result[1],
            'wind_speed_kmh': result[2],
            'humidity_percent': result[3]
        }
    return None

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    ingest_historical_weather(conn, start_date='2021-01-01')
    conn.close()
