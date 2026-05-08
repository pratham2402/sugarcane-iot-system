"""
fetch_context.py — Combines sensor data + weather into a single context dict.

This is the data that the agent will reason about.
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

BACKEND_URL = "http://localhost:8000"
WEATHER_API = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_API = "https://api.openweathermap.org/data/2.5/forecast"

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
LOCATION_LAT = os.getenv("LOCATION_LAT")
LOCATION_LON = os.getenv("LOCATION_LON")


def fetch_sensors():
    """Fetch the latest sensor reading from the Pi backend."""
    url = f"{BACKEND_URL}/latest-readings"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    data = response.json()
    nodes = data.get("nodes", [])
    if not nodes:
        return None
    return nodes[0]  # we only have 1 node


def fetch_current_weather():
    """Fetch current weather from OpenWeatherMap."""
    params = {
        "lat": LOCATION_LAT,
        "lon": LOCATION_LON,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }
    response = requests.get(WEATHER_API, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        "temp_c": data["main"]["temp"],
        "humidity_percent": data["main"]["humidity"],
        "conditions": data["weather"][0]["description"],
        "wind_speed_ms": data["wind"]["speed"],
        "rain_1h_mm": data.get("rain", {}).get("1h", 0),
        "pressure_mb": data["main"]["pressure"]
    }


def fetch_forecast():
    """Fetch the 5-day forecast (3-hour intervals) and summarize next 3 days."""
    params = {
        "lat": LOCATION_LAT,
        "lon": LOCATION_LON,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }
    response = requests.get(FORECAST_API, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Aggregate next ~3 days (24 entries × 3 hours = 72 hours)
    next_72h = data["list"][:24]

    total_rain = sum(entry.get("rain", {}).get("3h", 0) for entry in next_72h)
    avg_temp = sum(e["main"]["temp"] for e in next_72h) / len(next_72h)
    max_temp = max(e["main"]["temp"] for e in next_72h)
    min_temp = min(e["main"]["temp"] for e in next_72h)

    # Find first significant rain in forecast
    rain_in_next_72h = []
    for e in next_72h:
        rain_3h = e.get("rain", {}).get("3h", 0)
        if rain_3h > 0:
            rain_in_next_72h.append({
                "time": e["dt_txt"],
                "rain_mm": rain_3h
            })

    return {
        "next_72h_total_rain_mm": round(total_rain, 1),
        "next_72h_avg_temp_c": round(avg_temp, 1),
        "next_72h_max_temp_c": round(max_temp, 1),
        "next_72h_min_temp_c": round(min_temp, 1),
        "rain_events": rain_in_next_72h[:5]  # max 5 entries to keep it short
    }


def build_context():
    """Combine all data into a single context dict for the agent."""
    print("Fetching sensor data...")
    sensors = fetch_sensors()

    # Remove fields for sensors we don't have (rain gauge, flow meter)
    if sensors:
        sensors = {k: v for k, v in sensors.items() if v is not None}

    print("Fetching current weather...")
    weather = fetch_current_weather()

    print("Fetching 3-day forecast...")
    forecast = fetch_forecast()

    context = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "location": {
            "lat": float(LOCATION_LAT),
            "lon": float(LOCATION_LON),
            "name": "Pune, Maharashtra, India"
        },
        "crop": {
            "type": "sugarcane",
            "growth_stage": "tillering",  # placeholder — we'll improve later
            "days_after_planting": 90      # placeholder
        },
        "sensors": sensors,
        "weather_now": weather,
        "weather_forecast_72h": forecast
    }

    return context


def main():
    print("Building agent context...\n")

    try:
        context = build_context()
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # Pretty-print the context
    import json
    print("\n" + "=" * 60)
    print("AGENT CONTEXT:")
    print("=" * 60)
    print(json.dumps(context, indent=2, default=str))
    print("=" * 60)
    print("\n✅ Context built successfully!")


if __name__ == "__main__":
    main()
