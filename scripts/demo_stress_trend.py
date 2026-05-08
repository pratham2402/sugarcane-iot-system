"""
demo_stress_trend.py — Insert a gradual 4-day drying trend for demo purposes.

Why: the agent's anomaly detector flags sudden moisture drops as sensor faults.
To demo the irrigate path, we need a smooth multi-day decline so rolling
statistics adapt without flagging anomalies.

After demo: delete with
  DELETE FROM telemetry_readings WHERE firmware_version = 'demo-stress-test';
"""

import sqlite3
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path.home() / "sugarcane-iot-system-main" / "backend" / "data" / "telemetry.db"
NODE_ID = "node-01"

# 96 hours = 4 days, hourly readings
HOURS = 96

# Linear drying from 40% → 18% over 96 hours
START_MOISTURE = 40.0
END_MOISTURE = 18.0


def main():
    print(f"Inserting {HOURS} hourly readings (drying trend) into {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    end_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=HOURS)

    inserted = 0
    skipped = 0

    for h in range(HOURS + 1):
        ts_dt = start_time + timedelta(hours=h)
        ts = int(ts_dt.timestamp())

        # Linear drying with small random-looking variation
        progress = h / HOURS
        moisture = START_MOISTURE + (END_MOISTURE - START_MOISTURE) * progress
        # Tiny daily oscillation so it doesn't look perfectly linear
        oscillation = math.sin((h % 24) * math.pi / 12) * 0.5
        moisture = round(moisture + oscillation, 1)

        # Hot afternoons, cooler nights — realistic
        hour_of_day = ts_dt.hour
        air_temp = 30 + math.sin((hour_of_day - 5) * math.pi / 12) * 7
        air_temp = round(air_temp, 1)

        soil_temp = round(28 + math.sin((hour_of_day - 8) * math.pi / 12) * 3, 1)
        humidity = round(50 - math.sin((hour_of_day - 5) * math.pi / 12) * 10, 1)

        try:
            cursor.execute(
                """
                INSERT INTO telemetry_readings (
                    node_id, timestamp, firmware_version, battery_voltage, status,
                    soil_moisture, soil_moisture_valid,
                    soil_temperature, soil_temperature_valid,
                    air_temperature, air_temperature_valid,
                    humidity, humidity_valid,
                    rainfall_pulses, rainfall_pulses_valid,
                    flow_pulses, flow_pulses_valid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    NODE_ID, ts, "demo-stress-test", 3.75, "ok",
                    moisture, 1,
                    soil_temp, 1,
                    air_temp, 1,
                    humidity, 1,
                    None, 0,
                    None, 0,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Conflict with existing row at same timestamp
            skipped += 1

    conn.commit()
    conn.close()

    print(f"  Inserted: {inserted}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Final moisture: {END_MOISTURE}% (should trigger irrigate)")
    print(f"\nNow run: cd ../agent && python agent_graph.py")


if __name__ == "__main__":
    main()
