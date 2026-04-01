# 🌾 Sugarcane IoT Field Monitoring & Irrigation Intelligence System

> IoT-based telemetry platform for sugarcane farms — collecting environmental and soil data from distributed field sensors, aggregating through a local gateway, and forwarding to a cloud backend for storage, analysis, and decision support.

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PlatformIO](https://img.shields.io/badge/PlatformIO-ESP32-orange.svg)](https://platformio.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## System Architecture

```
┌─────────────────┐     LoRa      ┌──────────────────┐    HTTP     ┌─────────────────┐
│  ESP32 Node #1  │──────────────▶│                  │────────────▶│                 │
│  (Sensors)      │               │  Raspberry Pi    │             │  Cloud Backend  │
├─────────────────┤               │  Gateway         │             │  (FastAPI)      │
│  ESP32 Node #2  │──────────────▶│                  │             │                 │
│  (Sensors)      │               │  - LoRa Receiver │             │  - REST API     │
├─────────────────┤               │  - SQLite Store  │             │  - SQLite/PG    │
│  ESP32 Node #N  │──────────────▶│  - Upload Queue  │             │  - Telemetry    │
│  (Sensors)      │               │  - Retry Logic   │             │  - Analytics    │
└─────────────────┘               └──────────────────┘             └─────────────────┘
```

## Components

| Component | Directory | Language | Target Hardware | Status |
|-----------|-----------|----------|-----------------|--------|
| Edge Node Firmware | [`esp32-firmware/`](esp32-firmware/) | C++ (Arduino) | ESP32 DevKit | ✅ Built |
| Gateway Software | [`gateway/`](gateway/) | Python 3.9+ | Raspberry Pi | ✅ Built + Tested |
| Cloud Backend | [`backend/`](backend/) | Python 3.9+ (FastAPI) | Cloud Server | ✅ Built + Tested |
| Simulator | [`simulator/`](simulator/) | Python 3.9+ | Any machine | ✅ Verified |
| Data Contract | [`docs/`](docs/) | Markdown | — | ✅ Documented |

## Supported Sensors

| Sensor | Interface | Measurement |
|--------|-----------|-------------|
| Capacitive Soil Moisture | Analog (ADC) | Soil moisture 0–100% |
| DS18B20 Waterproof Probe | OneWire | Soil temperature (°C) |
| SHT31 Sensor | I2C | Air temperature + humidity |
| Rain Gauge (Tipping Bucket) | GPIO Interrupt | Rainfall (pulse count) |
| Water Flow Meter | GPIO Interrupt | Irrigation flow (pulse count) |

## Quick Start

### Prerequisites

- **Python 3.9+** (for gateway, backend, simulator)
- **PlatformIO** (for ESP32 firmware — optional for software dev)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/pratham2402/sugarcane-iot-system.git
cd sugarcane-iot-system
```

### 2. Start the Cloud Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit if needed

python -m app.main
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 3. Start the Gateway (Mock Mode)

```bash
cd gateway
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit if needed

python -m gateway.main --mock
```

### 4. Run End-to-End Simulation

```bash
cd simulator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python simulate_field.py --nodes 3 --rounds 10
```

### 5. Build ESP32 Firmware (Requires PlatformIO)

```bash
cd esp32-firmware
pio run                  # Build
pio run -t upload        # Flash to ESP32
pio device monitor       # Serial monitor
```

## Running Tests

```bash
# Backend tests (18 tests)
cd backend && source venv/bin/activate
python -m pytest tests/ -v

# Gateway tests (22 tests)
cd gateway && source venv/bin/activate
python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/telemetry/ingest` | Ingest single telemetry reading |
| `POST` | `/telemetry/ingest/batch` | Ingest batch of readings |
| `GET` | `/nodes` | List registered field nodes |
| `GET` | `/nodes/{node_id}` | Get specific node details |
| `GET` | `/latest-readings` | Latest reading per node |
| `GET` | `/readings` | Query with filters (node, time range) |

## Project Structure

```
sugarcane-iot-system/
├── esp32-firmware/          # ESP32 edge node firmware (C++)
│   ├── src/
│   │   ├── main.cpp         # Main loop & orchestration
│   │   ├── config.h         # Node configuration
│   │   ├── telemetry.*      # Payload builder
│   │   ├── sensors/         # Modular sensor drivers
│   │   ├── comms/           # Transport abstraction (LoRa/Serial)
│   │   └── utils/           # Validators, retry logic
│   └── platformio.ini
│
├── gateway/                 # Raspberry Pi gateway (Python)
│   ├── gateway/
│   │   ├── main.py          # Entry point
│   │   ├── receiver/        # LoRa + Mock receivers
│   │   ├── parser/          # Telemetry parsing & validation
│   │   ├── storage/         # SQLite persistence
│   │   ├── uploader/        # Cloud upload + retry queue
│   │   └── health/          # Health monitoring
│   └── tests/
│
├── backend/                 # Cloud backend (FastAPI)
│   ├── app/
│   │   ├── main.py          # FastAPI app factory
│   │   ├── api/             # Route handlers
│   │   ├── models/          # Pydantic schemas
│   │   └── db/              # Repository pattern
│   └── tests/
│
├── simulator/               # E2E simulation tools
│   ├── simulate_field.py    # Full pipeline simulator
│   └── mock_payloads.py     # Realistic data generator
│
├── docs/
│   └── data_contract.md     # Shared telemetry schema
│
└── .gitignore
```

## Data Contract

All components share a unified telemetry schema. See [`docs/data_contract.md`](docs/data_contract.md) for the full specification including:

- Compact (LoRa-optimized) and full payload formats
- Validation ranges for all sensor types
- Key mapping between compact and full keys
- Idempotency and optionality rules

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Offline-first** | Gateway stores all data locally before attempting cloud upload |
| **Fault-tolerant** | Handles sensor failures, packet loss, connectivity outages |
| **Modular** | Each sensor, transport, and storage layer is independently swappable |
| **Extensible** | Designed for future irrigation recommendations, alerts, actuator control |
| **Production-oriented** | Not a demo — structured for real field deployment |

## Contributing

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Ensure tests pass: `pytest tests/ -v`
4. Open a pull request with a description of changes

## License

Proprietary — Internal use only. All rights reserved.
