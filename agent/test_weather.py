"""
test_weather.py — Verify the OpenWeatherMap API key works.
Fetches current weather for Satara and prints relevant fields.
"""

import os
import requests
from dotenv import load_dotenv

# Load API keys + location from .env
load_dotenv()

api_key = os.getenv("OPENWEATHER_API_KEY")
lat = os.getenv("LOCATION_LAT")
lon = os.getenv("LOCATION_LON")

if not api_key:
    print("ERROR: OPENWEATHER_API_KEY not found in .env file")
    exit(1)

if not lat or not lon:
    print("ERROR: LOCATION_LAT or LOCATION_LON not found in .env file")
    exit(1)

print(f"API key loaded (starts with: {api_key[:8]}...)")
print(f"Location: lat={lat}, lon={lon}")

# OpenWeatherMap "Current Weather" endpoint
url = "https://api.openweathermap.org/data/2.5/weather"
params = {
    "lat": lat,
    "lon": lon,
    "appid": api_key,
    "units": "metric"  # gives temperature in Celsius
}

print("\nFetching current weather...")
response = requests.get(url, params=params, timeout=10)

if response.status_code != 200:
    print(f"ERROR: API returned status {response.status_code}")
    print(f"Response: {response.text}")
    exit(1)

data = response.json()

# Extract useful fields
city = data.get("name", "unknown")
temp = data["main"]["temp"]
humidity = data["main"]["humidity"]
description = data["weather"][0]["description"]
wind_speed = data["wind"]["speed"]

# Rainfall data — only present if it's currently raining
rain_1h = data.get("rain", {}).get("1h", 0)

print(f"\nWeather for {city}:")
print(f"  Temperature : {temp:.1f} °C")
print(f"  Humidity    : {humidity} %")
print(f"  Conditions  : {description}")
print(f"  Wind speed  : {wind_speed} m/s")
print(f"  Rain (1h)   : {rain_1h} mm")

print("\n✅ OpenWeatherMap API is working!")
