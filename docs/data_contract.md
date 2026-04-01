# Telemetry Data Contract

This document defines the unified telemetry payload schema shared across all system
components: ESP32 edge nodes, Raspberry Pi gateway, and cloud backend.

## Payload Structure

```json
{
  "node_id": "node-01",
  "timestamp": 1711929600,
  "firmware_version": "1.0.0",
  "battery_voltage": 3.72,
  "status": "ok",
  "readings": {
    "soil_moisture": {
      "value": 62.5,
      "unit": "%",
      "valid": true
    },
    "soil_temperature": {
      "value": 28.3,
      "unit": "°C",
      "valid": true
    },
    "air_temperature": {
      "value": 32.1,
      "unit": "°C",
      "valid": true
    },
    "humidity": {
      "value": 71.0,
      "unit": "%",
      "valid": true
    },
    "rainfall_pulses": {
      "value": 12,
      "unit": "pulses",
      "valid": true
    },
    "flow_pulses": {
      "value": 340,
      "unit": "pulses",
      "valid": true
    }
  }
}
```

## Field Definitions

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | string | Yes | Unique identifier for the ESP32 node (e.g., `"node-01"`) |
| `timestamp` | integer | Yes | Unix epoch seconds (UTC) when the reading was taken |
| `firmware_version` | string | No | Firmware version string (semver, e.g., `"1.0.0"`) |
| `battery_voltage` | float \| null | No | Battery voltage in volts (0.0–5.0V) |
| `status` | string | Yes | Node health status: `"ok"`, `"degraded"`, or `"error"` |
| `readings` | object | Yes | Container for sensor readings (may be empty `{}`) |

### Reading Fields

Each key in `readings` is a sensor type. Each value is an object with:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `value` | float \| integer | Yes | The sensor reading value |
| `unit` | string | Yes | Unit of measurement |
| `valid` | boolean | Yes | Whether the reading passed validation |

### Sensor Types & Validation

| Sensor Key | Value Type | Unit | Valid Range | Notes |
|------------|-----------|------|-------------|-------|
| `soil_moisture` | float | `%` | 0.0 – 100.0 | Capacitive sensor, mapped to percentage |
| `soil_temperature` | float | `°C` | -10.0 – 80.0 | DS18B20 waterproof probe |
| `air_temperature` | float | `°C` | -40.0 – 85.0 | SHT31 sensor |
| `humidity` | float | `%` | 0.0 – 100.0 | SHT31 sensor, relative humidity |
| `rainfall_pulses` | integer | `pulses` | 0 – 65535 | Tipping bucket counter since last report |
| `flow_pulses` | integer | `pulses` | 0 – 65535 | Flow meter counter since last report |

## Optionality Rules

- Not every node has every sensor. Only enabled sensors appear in `readings`.
- If a sensor is enabled but returns an error, include the reading with `"valid": false`
  and set `value` to the last known value or `0`.
- The `readings` object may be empty `{}` if all sensors failed.

## Status Values

| Status | Meaning |
|--------|---------|
| `ok` | All enabled sensors reading normally |
| `degraded` | One or more sensor readings are invalid |
| `error` | Critical failure — most or all sensors failed |

## Compact Payload (LoRa Optimization)

For LoRa transmission, payloads use shortened keys to reduce packet size:

```json
{
  "n": "node-01",
  "t": 1711929600,
  "fw": "1.0.0",
  "bv": 3.72,
  "s": "ok",
  "r": {
    "sm": [62.5, true],
    "st": [28.3, true],
    "at": [32.1, true],
    "hu": [71.0, true],
    "rp": [12, true],
    "fp": [340, true]
  }
}
```

The gateway expands compact payloads to full format before storage and upload.

### Compact Key Mapping

| Compact | Full Key |
|---------|----------|
| `n` | `node_id` |
| `t` | `timestamp` |
| `fw` | `firmware_version` |
| `bv` | `battery_voltage` |
| `s` | `status` |
| `r` | `readings` |
| `sm` | `soil_moisture` |
| `st` | `soil_temperature` |
| `at` | `air_temperature` |
| `hu` | `humidity` |
| `rp` | `rainfall_pulses` |
| `fp` | `flow_pulses` |

Reading values in compact format: `[value, valid]` (array instead of object).

## Idempotency

Telemetry records are uniquely identified by the combination of `(node_id, timestamp)`.
Duplicate submissions with the same key are safely ignored or updated.

## Future Extensions

The schema is designed to accommodate:
- Additional sensor types (add new keys to `readings`)
- Actuator status reporting
- Alert/event payloads (separate endpoint)
- GPS coordinates per node (add to top-level)
