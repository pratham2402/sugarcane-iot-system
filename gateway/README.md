# Raspberry Pi Gateway

Central field gateway software for receiving, storing, and forwarding
telemetry from ESP32 sensor nodes to the cloud backend.

## Overview

The gateway acts as:
- **LoRa receiver**: Captures packets from ESP32 field nodes
- **Local buffer**: Stores all data in SQLite (survives power cycles and internet outages)
- **Upload bridge**: Forwards telemetry to the cloud backend with retry logic
- **Health monitor**: Tracks receiver, storage, and upload subsystem status

## Architecture

```
gateway/
├── main.py                  # Entry point & orchestration
├── receiver/
│   ├── base_receiver.py     # Abstract receiver interface
│   ├── lora_receiver.py     # LoRa SX127x via SPI (RPi hardware)
│   └── mock_receiver.py     # Simulated packets for testing
├── parser/
│   └── telemetry_parser.py  # Compact ↔ full format + validation
├── storage/
│   ├── migrations.py        # SQLite schema & initialization
│   ├── models.py            # Typed row dataclasses
│   └── database.py          # Data access layer
├── uploader/
│   ├── cloud_uploader.py    # HTTP POST with error handling
│   └── retry_queue.py       # Background upload worker + backoff
├── health/
│   └── monitor.py           # Gateway health aggregator
└── utils/
    ├── logging_config.py    # Structured logging setup
    └── validators.py        # Validation helpers
```

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# On Raspberry Pi, also install hardware dependencies:
# pip install spidev RPi.GPIO
```

## Running

```bash
# Mock mode (for development without hardware)
python -m gateway.main --mock

# Production mode (uses config file receiver type)
python -m gateway.main

# With custom config
python -m gateway.main --config /path/to/config.yaml
```

## Configuration

Edit `config/gateway_config.yaml` to configure:

- **Receiver type**: `lora` or `mock`
- **LoRa parameters**: frequency, SF, BW (must match ESP32)
- **Database path**: SQLite file location
- **Cloud URL**: Backend API endpoint
- **Retry settings**: backoff, max retries, batch size
- **Health thresholds**: stale node timeout

## Data Flow

```
LoRa Packet → Raw Storage → Parse & Validate → Telemetry Storage → Upload Queue → Cloud
                                                       ↓
                                               Node Registry Update
```

1. Packet received via LoRa (or mock)
2. Raw bytes stored in `raw_packets` table
3. JSON parsed, compact keys expanded, values validated
4. Parsed record stored in `telemetry_readings` table
5. Record queued in `upload_queue` table
6. Upload worker sends to cloud with exponential backoff
7. Node registry updated for heartbeat tracking

## Database Schema

| Table | Purpose |
|-------|---------|
| `raw_packets` | Unprocessed received packets |
| `telemetry_readings` | Parsed and validated sensor data |
| `upload_queue` | Pending/completed cloud uploads |
| `node_registry` | Known node metadata and heartbeats |

## Offline Behavior

The gateway is designed for offline-first operation:

- All data is stored locally before any upload attempt
- If the cloud backend is unreachable, data accumulates in the upload queue
- The upload worker retries with exponential backoff (2s → 4s → 8s → ... → 5min cap)
- No data is lost during internet outages
- On reconnection, backlogged data is uploaded in order

## Testing

```bash
python -m pytest tests/ -v
```
