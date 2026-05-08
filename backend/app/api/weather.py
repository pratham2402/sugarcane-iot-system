"""
Weather API endpoint for the PWA.
Wraps OpenWeather data using the keys + coords already configured in .env.
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

router = APIRouter()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
LOCATION_LAT = os.getenv("LOCATION_LAT", "18.5204")
LOCATION_LON = os.getenv("LOCATION_LON", "73.8567")
WEATHER_API = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_API = "https://api.openweathermap.org/data/2.5/forecast"


class CurrentWeather(BaseModel):
    temp_c: float
    feels_like_c: float
    humidity_percent: float
    conditions: str
    main: str
    icon: str
    wind_speed_ms: float
    rain_1h_mm: float
    pressure_mb: int


class DailyForecast(BaseModel):
    date: str
    day_label: str
    temp_max_c: float
    temp_min_c: float
    rain_mm: float
    main: str
    icon: str
    conditions: str


class WeatherResponse(BaseModel):
    location_name: str
    current: CurrentWeather
    forecast: List[DailyForecast]


@router.get("/weather", response_model=WeatherResponse, tags=["Weather"])
async def get_weather():
    """
    Return current weather + 3-day forecast aggregated from OpenWeather.
    Used by the PWA dashboard to render the weather card.
    """
    if not OPENWEATHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENWEATHER_API_KEY not configured"
        )

    params = {
        "lat": LOCATION_LAT,
        "lon": LOCATION_LON,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    # Current
    try:
        r = requests.get(WEATHER_API, params=params, timeout=8)
        r.raise_for_status()
        cur = r.json()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch current weather: {e}"
        )

    current = CurrentWeather(
        temp_c=cur["main"]["temp"],
        feels_like_c=cur["main"].get("feels_like", cur["main"]["temp"]),
        humidity_percent=cur["main"]["humidity"],
        conditions=cur["weather"][0]["description"],
        main=cur["weather"][0]["main"],
        icon=cur["weather"][0]["icon"],
        wind_speed_ms=cur["wind"]["speed"],
        rain_1h_mm=cur.get("rain", {}).get("1h", 0),
        pressure_mb=cur["main"]["pressure"],
    )

    # Forecast (3-hourly) — group into daily buckets
    try:
        r2 = requests.get(FORECAST_API, params=params, timeout=8)
        r2.raise_for_status()
        fc = r2.json()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch forecast: {e}"
        )

    daily_buckets = {}

    for entry in fc.get("list", []):
        date = entry["dt_txt"][:10]

        if date not in daily_buckets:
            daily_buckets[date] = {
                "temps": [],
                "rains": [],
                "icons": [],
                "mains": [],
                "descriptions": [],
            }

        daily_buckets[date]["temps"].append(entry["main"]["temp"])
        daily_buckets[date]["rains"].append(
            entry.get("rain", {}).get("3h", 0)
        )
        daily_buckets[date]["icons"].append(
            entry["weather"][0]["icon"]
        )
        daily_buckets[date]["mains"].append(
            entry["weather"][0]["main"]
        )
        daily_buckets[date]["descriptions"].append(
            entry["weather"][0]["description"]
        )

    from datetime import datetime, timedelta, timezone

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sorted_dates = sorted(
        [d for d in daily_buckets.keys() if d >= today_str]
    )

    next_3 = sorted_dates[:3]

    day_labels = ["Today", "Tomorrow", "Day After"]

    forecast_list: List[DailyForecast] = []

    for i, date in enumerate(next_3):
        b = daily_buckets[date]

        # Pick midpoint icon/summary
        icon_choice = b["icons"][len(b["icons"]) // 2]
        main_choice = b["mains"][len(b["mains"]) // 2]
        desc_choice = b["descriptions"][len(b["descriptions"]) // 2]

        forecast_list.append(
            DailyForecast(
                date=date,
                day_label=day_labels[i] if i < len(day_labels) else date,
                temp_max_c=round(max(b["temps"]), 1),
                temp_min_c=round(min(b["temps"]), 1),
                rain_mm=round(sum(b["rains"]), 1),
                main=main_choice,
                icon=icon_choice,
                conditions=desc_choice,
            )
        )

    return WeatherResponse(
        location_name="Pune, Maharashtra",
        current=current,
        forecast=forecast_list,
    )
