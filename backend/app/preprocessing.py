"""
preprocessing.py — Data preprocessing for sensor readings.

Transforms raw hourly sensor data into:
  1. Cleaned data (anomalies flagged/removed)
  2. Daily aggregates (24 readings -> 1 daily summary)
  3. ML-ready feature vectors (rolling stats, growing degree days, etc.)

Used by:
  - The XGBoost yield model (consumes feature vectors)
  - The LangGraph agent (queries recent state + history)
  - The dashboard (shows daily trends)
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import numpy as np


# -------------------- CONFIGURATION --------------------
DB_PATH = Path(__file__).parent.parent / "data" / "telemetry.db"

# Sugarcane-specific thresholds
WATER_STRESS_THRESHOLD = 30.0   # below this, plant is under water stress (%)
GDD_BASE_TEMP = 10.0            # base temp for growing degree days (°C)


# -------------------- DATA LOADING --------------------

def load_readings(node_id: str = "node-01",
                  start: Optional[datetime] = None,
                  end: Optional[datetime] = None,
                  include_invalid: bool = False) -> pd.DataFrame:
    """
    Load sensor readings from SQLite as a pandas DataFrame.

    Args:
        node_id: Which node's data to load
        start: Earliest reading (UTC datetime). Defaults to 90 days ago.
        end: Latest reading (UTC datetime). Defaults to now.
        include_invalid: If False, exclude rows where any sensor was invalid.

    Returns:
        DataFrame with columns:
          timestamp, ingested_at, soil_moisture, soil_temperature,
          air_temperature, humidity, firmware_version
    """
    if start is None:
        start = datetime.now(timezone.utc) - timedelta(days=90)
    if end is None:
        end = datetime.now(timezone.utc)

    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT
            timestamp, ingested_at, firmware_version,
            soil_moisture, soil_moisture_valid,
            soil_temperature, soil_temperature_valid,
            air_temperature, air_temperature_valid,
            humidity, humidity_valid
        FROM telemetry_readings
        WHERE node_id = ?
          AND timestamp >= ?
          AND timestamp <= ?
        ORDER BY timestamp ASC
    """

    df = pd.read_sql_query(query, conn, params=(node_id, start_ts, end_ts))
    conn.close()

    # Convert timestamp to a proper datetime column for pandas resampling
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)

    if not include_invalid:
        # Drop rows where ANY sensor was invalid
        valid_mask = (
            (df["soil_moisture_valid"] == 1) &
            (df["soil_temperature_valid"] == 1) &
            (df["air_temperature_valid"] == 1) &
            (df["humidity_valid"] == 1)
        )
        df = df[valid_mask].copy()

    return df


# -------------------- ANOMALY DETECTION --------------------

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'is_anomaly' column flagging readings that look broken.

    Detection methods:
      1. Out-of-range values (impossible physical values)
      2. Rolling z-score (value differs >3 std deviations from local average)
      3. Stuck values (same reading for too many consecutive hours)

    Returns:
        DataFrame with added columns: is_anomaly, anomaly_reasons
    """
    df = df.copy()
    df["is_anomaly"] = False
    df["anomaly_reasons"] = ""

    # ---- Method 1: Range checks ----
    range_checks = [
        ("soil_moisture", 0, 100, "moisture out of range"),
        ("soil_temperature", -10, 60, "soil_temp out of range"),
        ("air_temperature", -10, 55, "air_temp out of range"),
        ("humidity", 0, 100, "humidity out of range"),
    ]

    for col, low, high, reason in range_checks:
        out_of_range = (df[col] < low) | (df[col] > high)
        df.loc[out_of_range, "is_anomaly"] = True
        df.loc[out_of_range, "anomaly_reasons"] += reason + "; "

    # ---- Method 2: Rolling z-score (only for big enough datasets) ----
    if len(df) > 24:
        for col in ["soil_moisture", "soil_temperature", "air_temperature", "humidity"]:
            window = 24  # 24-hour rolling window
            rolling_mean = df[col].rolling(window=window, min_periods=12).mean()
            rolling_std = df[col].rolling(window=window, min_periods=12).std()

            # z-score = how many std devs away from rolling mean
            z_scores = (df[col] - rolling_mean).abs() / rolling_std
            outliers = z_scores > 3.0  # >3 std devs = outlier

            df.loc[outliers.fillna(False), "is_anomaly"] = True
            df.loc[outliers.fillna(False), "anomaly_reasons"] += f"{col} statistical outlier; "

    # ---- Method 3: Stuck values (same reading for >6 consecutive hours) ----
    for col in ["soil_moisture", "soil_temperature", "humidity"]:
        same_as_prev = df[col].diff() == 0
        consecutive = same_as_prev.groupby((~same_as_prev).cumsum()).cumsum()
        stuck = consecutive >= 6
        df.loc[stuck, "is_anomaly"] = True
        df.loc[stuck, "anomaly_reasons"] += f"{col} stuck; "

    return df


# -------------------- DAILY AGGREGATION --------------------

def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate hourly readings into daily summaries.

    Returns:
        DataFrame with one row per day, indexed by date.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df = df.set_index("datetime")

    # Group by date, compute aggregations
    daily = df.resample("D").agg({
        "soil_moisture": ["mean", "min", "max"],
        "soil_temperature": ["mean", "min", "max"],
        "air_temperature": ["mean", "min", "max"],
        "humidity": ["mean"],
    })

    # Flatten the multi-level column names
    daily.columns = ["_".join(col) for col in daily.columns]

    # Add count of readings per day (data quality indicator)
    daily["reading_count"] = df.resample("D").size()

    # Round all numeric values for readability
    daily = daily.round(2)

    return daily


# -------------------- FEATURE ENGINEERING --------------------

def compute_features(df: pd.DataFrame,
                     days_after_planting: int = 90,
                     rainfall_30d_mm: float = 50.0) -> dict:
    """
    Compute ML-ready feature vector from recent sensor history.

    These are the features the XGBoost yield model expects.

    Args:
        df: Recent readings DataFrame (typically last 30 days)
        days_after_planting: Crop age in days (manual input or from crop calendar)
        rainfall_30d_mm: Total rainfall in last 30 days (from weather API in production)

    Returns:
        Dict of features (single row, ready for model.predict)
    """
    if df.empty:
        return {}

    # Time-based features
    avg_moisture = df["soil_moisture"].mean()
    avg_soil_temp = df["soil_temperature"].mean()
    avg_air_temp = df["air_temperature"].mean()
    avg_humidity = df["humidity"].mean()

    # Variability (how much the values fluctuate)
    moisture_std = df["soil_moisture"].std()
    temp_std = df["air_temperature"].std()

    # Stress indicators
    days_under_stress = (df["soil_moisture"] < WATER_STRESS_THRESHOLD).sum() / 24.0
    extreme_heat_hours = (df["air_temperature"] > 38).sum()

    # Growing Degree Days (GDD): cumulative warmth above base temperature
    # Real agronomic feature for crop growth modeling
    daily_avg_temp = df.set_index("datetime")["air_temperature"].resample("D").mean()
    gdd = (daily_avg_temp - GDD_BASE_TEMP).clip(lower=0).sum()

    # Crop stage (categorical, depends on days after planting)
    if days_after_planting < 30:
        crop_stage = "germination"
    elif days_after_planting < 130:
        crop_stage = "tillering"
    elif days_after_planting < 250:
        crop_stage = "grand_growth"
    elif days_after_planting < 360:
        crop_stage = "maturation"
    else:
        crop_stage = "harvest"

    return {
        "avg_soil_moisture": round(float(avg_moisture), 2),
        "avg_soil_temperature": round(float(avg_soil_temp), 2),
        "avg_air_temperature": round(float(avg_air_temp), 2),
        "avg_humidity": round(float(avg_humidity), 2),
        "moisture_std": round(float(moisture_std), 2),
        "temp_std": round(float(temp_std), 2),
        "days_under_water_stress": round(float(days_under_stress), 1),
        "extreme_heat_hours": int(extreme_heat_hours),
        "growing_degree_days": round(float(gdd), 1),
        "rainfall_30d_mm": float(rainfall_30d_mm),
        "days_after_planting": days_after_planting,
        "crop_stage": crop_stage,
    }


# -------------------- HIGH-LEVEL API --------------------

def get_clean_recent_data(node_id: str = "node-01",
                          days: int = 30) -> pd.DataFrame:
    """
    Get cleaned, anomaly-flagged recent data.
    Convenience function for the agent and ML model.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = load_readings(node_id=node_id, start=start, end=end)
    df = detect_anomalies(df)

    # Drop anomalies for downstream use (or keep them flagged — your call)
    clean_df = df[~df["is_anomaly"]].copy()

    return clean_df


def get_feature_vector(node_id: str = "node-01",
                       days_after_planting: int = 90,
                       rainfall_30d_mm: float = 50.0) -> dict:
    """
    One-stop function: get ML feature vector for current state.
    Used by the agent before calling the yield model.
    """
    df = get_clean_recent_data(node_id=node_id, days=30)
    return compute_features(df, days_after_planting, rainfall_30d_mm)


# -------------------- DEMO / SELF-TEST --------------------

def main():
    """Run preprocessing and print summaries — for testing."""
    print("=" * 60)
    print("PREPROCESSING SELF-TEST")
    print("=" * 60)
    print(f"Database: {DB_PATH}\n")

    # 1. Load 30 days of clean data
    print("[1] Loading last 30 days of readings...")
    df = get_clean_recent_data(days=30)
    print(f"    Loaded {len(df)} clean rows from last 30 days\n")

    if df.empty:
        print("    No data — make sure backend ran or run generate_history.py first.")
        return

    # 2. Anomaly detection (re-run on the full unfiltered data for visibility)
    print("[2] Detecting anomalies on full last-30-days dataset...")
    df_with_anomalies = load_readings(
        start=datetime.now(timezone.utc) - timedelta(days=30)
    )
    df_with_anomalies = detect_anomalies(df_with_anomalies)
    n_anomalies = df_with_anomalies["is_anomaly"].sum()
    print(f"    Flagged {n_anomalies} anomalies out of {len(df_with_anomalies)} readings\n")

    if n_anomalies > 0:
        print("    Sample anomalies:")
        sample = df_with_anomalies[df_with_anomalies["is_anomaly"]].head(3)
        for _, row in sample.iterrows():
            print(f"      {row['ingested_at']}  soil_moisture={row['soil_moisture']:.1f}, "
                  f"soil_temp={row['soil_temperature']:.1f} -> {row['anomaly_reasons']}")
        print()

    # 3. Daily aggregation
    print("[3] Aggregating to daily summaries...")
    daily = aggregate_daily(df)
    print(f"    Got {len(daily)} daily summaries")
    print(f"    Last 5 days:")
    print(daily.tail(5).to_string())
    print()

    # 4. Feature vector for the ML model
    print("[4] Computing ML feature vector...")
    features = compute_features(df,
                                days_after_planting=90,
                                rainfall_30d_mm=50.0)
    print("    Feature vector:")
    for k, v in features.items():
        print(f"      {k}: {v}")
    print()

    print("=" * 60)
    print("SELF-TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
