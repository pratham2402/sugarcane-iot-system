"""
generate_history.py — Insert 90 days of plausible sensor history into SQLite.

Realistic for Maharashtra Jan-Apr (pre-monsoon hot season).
Sugarcane in tillering/grand-growth stage.
"""

import sqlite3
import random
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

# -------------------- CONFIGURATION --------------------
DB_PATH = Path.home() / "sugarcane-iot-system-main" / "backend" / "data" / "telemetry.db"
NODE_ID = "node-01"
DAYS_OF_HISTORY = 90
READINGS_PER_DAY = 24
FIRMWARE_VERSION = "0.4.5-historical"


# -------------------- AGRONOMIC MODELING --------------------

def simulate_day(day_number, days_total):
    """
    Simulate one day's pattern for Maharashtra Jan-Apr.
    Returns (rainfall_mm, season_temp_offset).

    Reality of Maharashtra Jan-Apr:
      - January: cooler (~25-32°C), dry
      - February: warming (~28-34°C), dry
      - March: hot (~30-37°C), occasional pre-monsoon shower
      - April: very hot (~32-39°C), occasional thunderstorm

    Rain is rare but not zero — pre-monsoon showers happen.
    """
    # Rain probability rises later in the season (pre-monsoon)
    progress = day_number / days_total  # 0.0 to 1.0
    rain_prob = 0.05 + 0.15 * progress  # 5% in Jan, 20% by Apr
    has_rain = random.random() < rain_prob

    rainfall_mm = 0
    if has_rain:
        rainfall_mm = random.uniform(5, 30)  # 5-30mm when it rains

    # Temperature progression: cooler at start, hotter at end
    # Day 0 (Jan 28): -3°C from average
    # Day 90 (Apr 28): +3°C from average
    season_temp_offset = -3 + 6 * progress
    return rainfall_mm, season_temp_offset


def simulate_hourly_reading(day_offset, hour, last_moisture, daily_rainfall, season_temp_offset):
    """Generate one hourly reading with realistic Maharashtra patterns."""

    # ---- Air temperature ----
    # Maharashtra avg is ~30°C; daily swing 7°C (cooler nights, hot afternoons)
    base_temp = 31  # higher base for sugarcane belt
    daily_swing = 7
    hour_offset = math.sin((hour - 5) * math.pi / 12) * daily_swing
    air_temp = base_temp + hour_offset + season_temp_offset + random.uniform(-1, 1)
    air_temp = round(air_temp, 1)

    # ---- Air humidity ----
    # Inversely correlated with temp; lower in dry season
    base_humidity = 50  # Pune in dry season
    humidity = base_humidity - hour_offset * 1.5 + random.uniform(-3, 3)
    humidity = max(15, min(85, humidity))
    humidity = round(humidity, 1)

    # ---- Soil temperature ----
    # Soil is dampened/lagged version of air temperature
    soil_temp_swing = daily_swing * 0.4
    soil_offset = math.sin((hour - 8) * math.pi / 12) * soil_temp_swing
    soil_temp = base_temp + soil_offset + season_temp_offset + random.uniform(-0.5, 0.5)
    soil_temp = round(soil_temp, 2)

    # ---- Soil moisture ----
    # Sugarcane fields are typically irrigated to keep moisture in 40-60%
    # Without irrigation: drying rate ~0.15% per hour (slower than my old script)
    drying_rate = 0.15
    new_moisture = last_moisture - drying_rate

    # Rainfall boost (afternoon hours)
    if daily_rainfall > 0 and 12 <= hour <= 18:
        moisture_boost_per_hour = daily_rainfall * 0.6 / 7
        new_moisture += moisture_boost_per_hour

    # Simulate periodic irrigation (every 4-7 days, the farmer "irrigates")
    # In production this would be the agent's decisions; for synthetic data
    # we add a periodic boost when moisture drops below 30%
    if new_moisture < 30 and random.random() < 0.4:
        new_moisture += random.uniform(20, 30)  # irrigation event

    # Clamp realistic range
    new_moisture = max(15, min(75, new_moisture))
    new_moisture = round(new_moisture, 1)

    return {
        "soil_temperature": soil_temp,
        "air_temperature": air_temp,
        "humidity": humidity,
        "soil_moisture": new_moisture
    }


def maybe_inject_anomaly(reading, anomaly_chance=0.005):
    """With small probability, corrupt a reading. Returns (reading, was_anomaly)."""
    if random.random() > anomaly_chance:
        return reading, False

    anomaly_type = random.choice(["spike", "drop", "stuck_high"])

    if anomaly_type == "spike":
        reading["soil_temperature"] = 79.5 + random.random()
    elif anomaly_type == "drop":
        reading["soil_moisture"] = 0.1
    elif anomaly_type == "stuck_high":
        reading["humidity"] = 100.0

    return reading, True


# -------------------- DATABASE INSERTION --------------------

def insert_readings(readings):
    """Insert generated readings into SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='telemetry_readings'
    """)
    if not cursor.fetchone():
        print("ERROR: telemetry_readings table not found.")
        conn.close()
        return 0, 0

    inserted_count = 0
    skipped_count = 0

    for r in readings:
        try:
            cursor.execute("""
                INSERT INTO telemetry_readings (
                    node_id, timestamp, firmware_version, battery_voltage, status,
                    soil_moisture, soil_moisture_valid,
                    soil_temperature, soil_temperature_valid,
                    air_temperature, air_temperature_valid,
                    humidity, humidity_valid,
                    rainfall_pulses, rainfall_pulses_valid,
                    flow_pulses, flow_pulses_valid,
                    ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["node_id"],
                r["timestamp"],
                r["firmware_version"],
                r["battery_voltage"],
                r["status"],
                r["soil_moisture"], 1,
                r["soil_temperature"], 1,
                r["air_temperature"], 1,
                r["humidity"], 1,
                None, 0,
                None, 0,
                r["ingested_at"]
            ))
            inserted_count += 1
        except sqlite3.IntegrityError:
            skipped_count += 1

    conn.commit()
    conn.close()
    return inserted_count, skipped_count


# -------------------- MAIN --------------------

def main():
    print("=" * 60)
    print("Generating synthetic sugarcane field history")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Node ID:  {NODE_ID}")
    print(f"Days:     {DAYS_OF_HISTORY}")
    print(f"Readings: {DAYS_OF_HISTORY * READINGS_PER_DAY} hourly samples")
    print()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    end_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=DAYS_OF_HISTORY)

    print(f"Generating readings from {start_time.date()} to {end_time.date()}...\n")

    last_moisture = 50.0
    readings = []
    anomaly_count = 0

    for day in range(DAYS_OF_HISTORY):
        rainfall_mm, season_temp_offset = simulate_day(day, DAYS_OF_HISTORY)

        for hour in range(READINGS_PER_DAY):
            timestamp_dt = start_time + timedelta(days=day, hours=hour)

            reading_values = simulate_hourly_reading(
                day, hour, last_moisture, rainfall_mm, season_temp_offset
            )

            reading_values, was_anomaly = maybe_inject_anomaly(reading_values)
            if was_anomaly:
                anomaly_count += 1

            last_moisture = reading_values["soil_moisture"]

            reading = {
                "node_id": NODE_ID,
                "timestamp": int(timestamp_dt.timestamp()),
                "firmware_version": FIRMWARE_VERSION,
                "battery_voltage": round(3.7 + random.uniform(-0.1, 0.1), 2),
                "status": "ok",
                "soil_temperature": reading_values["soil_temperature"],
                "air_temperature": reading_values["air_temperature"],
                "humidity": reading_values["humidity"],
                "soil_moisture": reading_values["soil_moisture"],
                "ingested_at": timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
            }
            readings.append(reading)

    print(f"Inserting {len(readings)} readings...")
    inserted, skipped = insert_readings(readings)

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Inserted: {inserted}")
    print(f"Skipped (duplicates): {skipped}")
    print(f"Anomalies injected:   {anomaly_count}")
    print()
    print("Sample of generated data:")
    print(f"  First (oldest): {readings[0]['ingested_at']}")
    print(f"    soil_moisture={readings[0]['soil_moisture']}%, "
          f"soil_temp={readings[0]['soil_temperature']} C, "
          f"air_temp={readings[0]['air_temperature']} C")
    print(f"  Last (newest): {readings[-1]['ingested_at']}")
    print(f"    soil_moisture={readings[-1]['soil_moisture']}%, "
          f"soil_temp={readings[-1]['soil_temperature']} C, "
          f"air_temp={readings[-1]['air_temperature']} C")


if __name__ == "__main__":
    main()
