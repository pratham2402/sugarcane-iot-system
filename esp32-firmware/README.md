# ESP32 Edge Node Firmware

Sugarcane Field Monitor firmware for ESP32-based sensor nodes.

## Overview

Each ESP32 node reads from its connected sensors, builds a compact JSON
telemetry payload, and transmits it via LoRa to the Raspberry Pi gateway.

## Supported Sensors

| Sensor | Interface | Config Flag |
|--------|-----------|-------------|
| Capacitive Soil Moisture | Analog (ADC) | `SENSOR_SOIL_MOISTURE_ENABLED` |
| DS18B20 Soil Temperature | OneWire | `SENSOR_DS18B20_ENABLED` |
| SHT31 Air Temp + Humidity | I2C | `SENSOR_SHT31_ENABLED` |
| Rain Gauge (Tipping Bucket) | GPIO Interrupt | `SENSOR_RAIN_GAUGE_ENABLED` |
| Water Flow Meter | GPIO Interrupt | `SENSOR_FLOW_METER_ENABLED` |

## Configuration

Edit `src/config.h` before flashing:

1. Set `NODE_ID` to a unique identifier (e.g., `"node-01"`, `"node-02"`)
2. Enable/disable sensors based on what's connected
3. Adjust pin assignments to match your wiring
4. Calibrate `SOIL_MOISTURE_AIR` and `SOIL_MOISTURE_WATER` for your sensor
5. Set `LORA_FREQUENCY` for your region (433/868/915 MHz)
6. Set `TRANSPORT_MODE` to `"serial"` for bench testing without LoRa

## Building & Flashing

Requires [PlatformIO](https://platformio.org/).

```bash
# Build
pio run

# Flash to connected ESP32
pio run -t upload

# Open serial monitor
pio device monitor -b 115200
```

## Wiring Reference

### Default Pin Assignments

| Component | GPIO | Notes |
|-----------|------|-------|
| Soil Moisture | 34 | ADC1 CH6 |
| DS18B20 | 4 | OneWire data, 4.7kΩ pull-up |
| SHT31 SDA | 21 | I2C default |
| SHT31 SCL | 22 | I2C default |
| Rain Gauge | 16 | Interrupt, pull-up |
| Flow Meter | 17 | Interrupt, pull-up |
| Battery Voltage | 35 | ADC1 CH7, voltage divider |
| LoRa CS/NSS | 5 | SPI |
| LoRa DIO0 | 2 | IRQ |
| LoRa RST | 14 | Reset |

### LoRa Module (SX1278)

Connect to ESP32 default SPI pins:
- MOSI → GPIO 23
- MISO → GPIO 19
- SCK → GPIO 18
- CS → GPIO 5 (configurable)

## Payload Format

Compact JSON with short keys (see `docs/data_contract.md`):

```json
{"n":"node-01","t":60,"fw":"1.0.0","s":"ok","r":{"sm":[62.5,true],"st":[28.3,true],"at":[32.1,true],"hu":[71.0,true]}}
```

## Architecture

```
main.cpp            → Setup + main loop orchestration
├── config.h        → All configuration constants
├── telemetry.*     → Payload builder
├── sensors/
│   ├── sensor_interface.h  → Abstract ISensor base
│   ├── soil_moisture.*     → Capacitive sensor
│   ├── ds18b20.*           → OneWire temp probe
│   ├── sht31.*             → SHT31 driver + adapters
│   ├── rain_gauge.*        → Tipping bucket ISR
│   └── flow_meter.*        → Flow sensor ISR
├── comms/
│   ├── transport.h         → Abstract ITransport base
│   ├── lora_transport.*    → SX1278 via RadioLib
│   └── serial_transport.*  → Serial debug transport
└── utils/
    ├── validators.h        → Range/value validation
    └── retry.*             → Transmission retry logic
```
