"""
Backend validation utilities.
"""

VALIDATION_RANGES = {
    "soil_moisture": (0.0, 100.0),
    "soil_temperature": (-10.0, 80.0),
    "air_temperature": (-40.0, 85.0),
    "humidity": (0.0, 100.0),
    "rainfall_pulses": (0, 65535),
    "flow_pulses": (0, 65535),
}


def validate_reading_value(sensor_type: str, value: float) -> bool:
    """Check if a sensor reading is within the expected range."""
    if sensor_type in VALIDATION_RANGES:
        min_val, max_val = VALIDATION_RANGES[sensor_type]
        return min_val <= value <= max_val
    return True  # Unknown sensor types pass validation
