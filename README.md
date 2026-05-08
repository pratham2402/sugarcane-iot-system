# 🌾 Sugarcane IoT Field Monitoring & Irrigation Intelligence System

> End-to-end IoT platform for sugarcane farms: real-time sensor telemetry from ESP32 nodes, a Raspberry Pi gateway running an LLM-powered irrigation agent, a FastAPI cloud backend with ML-based yield prediction, and a farmer-facing PWA dashboard with AI chat support.

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PlatformIO](https://img.shields.io/badge/PlatformIO-ESP32-orange.svg)](https://platformio.org/)
[![Vite](https://img.shields.io/badge/Vite-PWA-646CFF.svg)](https://vitejs.dev/)
[![Gemini](https://img.shields.io/badge/Gemini-AI-4285F4.svg)](https://ai.google.dev/)

---

## System Architecture

```
   ┌─────────────────┐    WiFi/HTTP    ┌──────────────────────┐    HTTPS    ┌─────────────────┐
   │  ESP32 Node #1  │────────────────▶│                      │────────────▶│                 │
   │  Soil + Air     │                 │  Raspberry Pi        │             │  Cloud Backend  │
   ├─────────────────┤                 │  Gateway             │             │  (FastAPI)      │
   │  ESP32 Node #2  │────────────────▶│                      │             │                 │
   │  Soil + Air     │                 │  - Telemetry Ingest  │             │  - REST API     │
   ├─────────────────┤                 │  - SQLite Storage    │             │  - Yield ML     │
   │  ESP32 Node #N  │────────────────▶│  - Cloud Uploader    │             │  - Anomaly Det. │
   │  Soil + Air     │                 │  - Gemini AI Agent   │             │  - Weather API  │
   └─────────────────┘                 │  - Health Monitor    │             │  - Valve Control│
                                       └──────────┬───────────┘             └────────┬────────┘
                                                  │                                  │
                                                  │ Cloudflare Tunnel                │
                                                  ▼                                  ▼
                                       ┌──────────────────────────────────────────────────┐
                                       │             Farmer Web App (PWA)                  │
                                       │   Dashboard · AI Chat · Valve Control · Yield     │
                                       └──────────────────────────────────────────────────┘
```

---

## Components

| Component | Directory | Language / Stack | Target | Description |
|-----------|-----------|------------------|--------|-------------|
| Edge Node Firmware | [`esp32-firmware/`](esp32-firmware) | C++ (Arduino) | ESP32 DevKit | WiFi-based telemetry over HTTP to gateway |
| Raspberry Pi Gateway | [`gateway/`](gateway) | Python 3.9+ | Raspberry Pi | Local ingest, storage, cloud relay |
| AI Decision Agent | [`agent/`](agent) | Python 3.9+ (LangGraph + Gemini) | Raspberry Pi | LLM-driven irrigation diagnosis & decisions |
| Cloud Backend | [`backend/`](backend) | Python 3.9+ (FastAPI) | Cloud Server | REST API, ML yield prediction, anomaly detection |
| Web App | [`webapp/`](webapp) | Vite + Vanilla JS (PWA) | Browser | Farmer dashboard, AI chat, valve control |
| Simulator | [`simulator/`](simulator) | Python 3.9+ | Any machine | Synthetic telemetry for E2E testing |
| Demo Scripts | [`scripts/`](scripts) | Python 3.9+ | Any machine | Stress-trend demo & history generator |
| Data Contract | [`docs/`](docs) | Markdown | — | Shared telemetry schema |

---

## Hardware

### ESP32 Edge Node

| Sensor | Interface | Pin | Measurement |
|--------|-----------|-----|-------------|
| DS18B20 Waterproof Probe | OneWire | GPIO 4 | Soil temperature (°C) |
| DHT11 | Digital | GPIO 19 | Air temperature + humidity |
| RS485 Soil Moisture (Modbus) | UART2 (with MAX485) | RX 16 / TX 17 / DE+RE 14 | Soil moisture (0–100%) |

> **Communication:** Each ESP32 connects to the local WiFi network and posts JSON telemetry directly to the Raspberry Pi gateway over HTTP.

### Raspberry Pi Gateway

- Hosts the FastAPI gateway service (telemetry ingest endpoint)
- Runs the LLM agent for periodic irrigation decisions
- Maintains a local SQLite store and a retry queue for cloud uploads
- Exposes the webapp's backend via Cloudflare Tunnel

---

## Quick Start

### Prerequisites

- **Python 3.9+** (gateway, backend, agent, simulator)
- **Node.js 18+** (web app)
- **PlatformIO** (ESP32 firmware, optional for software-only dev)
- **Git**

### 1. Clone the repository

```bash
git clone https://github.com/pratham2402/sugarcane-iot-system.git
cd sugarcane-iot-system
```

### 2. Cloud Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in DB / API keys
python -m app.main
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 3. Raspberry Pi Gateway

```bash
cd gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in cloud backend URL + auth token
python -m gateway.main
```

### 4. AI Agent (on Raspberry Pi)

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Create a .env file with:
#   GEMINI_API_KEY=your_key_here
#   OPENWEATHER_API_KEY=your_key_here
bash run_agent.sh
```

### 5. ESP32 Firmware

Open `esp32-firmware/src/main_wifi.cpp` and set your WiFi credentials and gateway URL:

```cpp
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* BACKEND_URL = "http://sugarcanepi.local:8000/telemetry/ingest";
```

Then flash:

```bash
cd esp32-firmware
pio run                 # build
pio run -t upload       # flash
pio device monitor      # serial output
```

### 6. Web App (PWA)

```bash
cd webapp
npm install
cp .env.example .env.local    # add GEMINI_API_KEY for AI chat
npm run dev
# Local:  http://localhost:5173
```

### 7. End-to-End Simulation

```bash
cd simulator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python simulate_field.py --nodes 3 --rounds 10
```

---

## API Endpoints (Cloud Backend)

### Telemetry & Nodes
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Service health check |
| `POST` | `/telemetry/ingest` | Ingest single telemetry reading |
| `POST` | `/telemetry/ingest/batch` | Ingest batch of readings |
| `GET`  | `/nodes` | List registered field nodes |
| `GET`  | `/nodes/{node_id}` | Specific node details |
| `GET`  | `/latest-readings` | Latest reading per node |
| `GET`  | `/readings` | Filtered query (node + time range) |

### Intelligence
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/anomalies` | Detected sensor / field anomalies |
| `GET`  | `/yield/predict` | ML-based yield prediction |
| `GET`  | `/weather` | Current + forecast weather |
| `POST` | `/valve/control` | Open/close irrigation valve |
| `GET`  | `/valve/history` | Valve actuation history |

> Authentication uses bearer tokens. See `backend/app/auth.py`.

---

## AI Agent

The agent (`agent/`) runs on the Raspberry Pi and performs scheduled irrigation diagnosis:

- **Inputs:** latest sensor readings, recent history, weather forecast
- **Reasoning:** LangGraph-based pipeline using Google Gemini
- **Outputs:** stress assessment, irrigation recommendation, valve action
- **Test scripts:** `test_gemini.py`, `test_weather.py`

The web app's AI chat feature talks to Gemini through a serverless function (`webapp/api/chat.js`), keeping the API key server-side.

---

## Yield Prediction

The backend ships a trained ML model:

- `backend/yield_model.pkl` — serialized regressor
- `backend/feature_columns.pkl` — expected feature order
- `backend/model_metadata.json` — training metadata
- `backend/app/preprocessing.py` — feature engineering pipeline
- `backend/app/yield_prediction.py` — inference logic
- `backend/app/api/yield_prediction.py` — REST endpoint

Use `scripts/generate_history.py` to produce synthetic historical data for retraining.

---

## Web App Features

The PWA (`webapp/`) is the farmer-facing interface:

- **Live Dashboard** — soil moisture, temperatures, humidity, rainfall, flow
- **AI Chat (Gemini)** — diagnose, digest, and ask farming questions
- **Valve Control** — manual + history, with token-based auth
- **Yield Forecast** — estimated yield from current conditions
- **PWA Install** — works offline with service worker
- **Backend Token** — paste a bearer token to authenticate with the gateway

---

## Project Structure

```
sugarcane-iot-system/
├── esp32-firmware/              # ESP32 edge node firmware (C++)
│   └── src/
│       ├── main_wifi.cpp        # WiFi-based telemetry (active)
│       ├── main.cpp             # LoRa variant (legacy)
│       ├── config.h             # Pin & config constants
│       ├── sensors/             # DS18B20, DHT, RS485 soil moisture
│       ├── comms/               # Transport abstraction
│       └── utils/               # Validators, retry helpers
│
├── gateway/                     # Raspberry Pi gateway (Python)
│   └── gateway/
│       ├── main.py              # Entry point
│       ├── receiver/            # Telemetry ingestion
│       ├── parser/              # Schema validation
│       ├── storage/             # SQLite persistence
│       ├── uploader/            # Cloud upload + retry queue
│       └── health/              # Self-monitoring
│
├── agent/                       # AI irrigation agent
│   ├── agent.py                 # Agent runner
│   ├── agent_graph.py           # LangGraph pipeline
│   ├── fetch_context.py         # Weather + history context
│   ├── fetch_sensors.py         # Live sensor pull
│   ├── run_agent.sh             # Cron-friendly launcher
│   └── test_*.py                # Smoke tests
│
├── backend/                     # Cloud backend (FastAPI)
│   └── app/
│       ├── main.py              # FastAPI app factory
│       ├── auth.py              # Bearer-token auth
│       ├── api/                 # Route handlers
│       │   ├── telemetry.py
│       │   ├── nodes.py
│       │   ├── readings.py
│       │   ├── anomalies.py
│       │   ├── valve.py
│       │   ├── weather.py
│       │   └── yield_prediction.py
│       ├── models/              # Pydantic + DB schemas
│       ├── db/                  # Repository pattern
│       ├── preprocessing.py     # ML feature pipeline
│       └── yield_prediction.py  # ML inference
│
├── webapp/                      # Farmer-facing PWA
│   ├── src/
│   │   ├── main.js              # Dashboard, chat, valve UI
│   │   └── style.css
│   ├── api/
│   │   └── chat.js              # Gemini proxy (Vercel-style)
│   ├── public/                  # PWA icons + manifest
│   ├── index.html
│   └── vite.config.js
│
├── simulator/                   # E2E simulation tools
│   ├── simulate_field.py
│   └── mock_payloads.py
│
├── scripts/                     # Demo & data utilities
│   ├── demo_stress_trend.py
│   └── generate_history.py
│
├── docs/
│   └── data_contract.md         # Shared telemetry schema
│
└── .gitignore
```

---

## Data Contract

All components share a unified telemetry schema. See [`docs/data_contract.md`](docs/data_contract.md) for the full specification: full / compact payloads, validation ranges, and key mapping rules.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Offline-first** | Gateway stores all data locally before attempting cloud upload |
| **Fault-tolerant** | Handles sensor failures, packet loss, connectivity outages |
| **Modular** | Each sensor, transport, and storage layer is independently swappable |
| **Edge-intelligent** | Decision-making (LLM agent) runs at the edge for low latency and resilience |
| **Secrets-out-of-code** | All API keys live in `.env` files; only `.env.example` placeholders are committed |
| **Production-oriented** | Structured for real field deployment, not just a demo |

---

## Environment Variables

Each component has its own `.env.example`. Copy it to `.env` (or `.env.local` for the webapp) and fill in your values. Real `.env` files are gitignored.

| Component | Required Keys |
|-----------|---------------|
| `backend/.env` | DB connection, auth secret |
| `gateway/.env` | Backend URL, bearer token |
| `agent/.env` | `GEMINI_API_KEY`, `OPENWEATHER_API_KEY` |
| `webapp/.env.local` | `GEMINI_API_KEY` (server-side proxy only) |

---

## Tests

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -v
cd gateway && source .venv/bin/activate && python -m pytest tests/ -v
```

---

## License

Proprietary. Internal use only. All rights reserved.
