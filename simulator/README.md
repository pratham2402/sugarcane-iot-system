# End-to-End Simulator

Simulates the complete sugarcane field monitoring pipeline without hardware.

## Purpose

This simulator validates the end-to-end data flow:

```
Mock ESP32 Payloads → Backend API → Database → Query APIs
```

It generates realistic telemetry data that mimics actual field conditions,
sends it to the cloud backend, and verifies the data appears correctly.

## Usage

### Prerequisites

Start the cloud backend first:
```bash
cd ../backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

### Run Simulation

```bash
# Install simulator dependencies
pip install -r requirements.txt

# Run with defaults (3 nodes, 10 rounds)
python simulate_field.py

# Customize
python simulate_field.py --nodes 5 --rounds 20 --interval 1.0

# Against remote backend
python simulate_field.py --url http://your-server:8000
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | `http://localhost:8000` | Backend API URL |
| `--nodes` | 3 | Number of simulated nodes |
| `--rounds` | 10 | Number of simulation rounds |
| `--interval` | 2.0 | Seconds between rounds |

## Components

### `mock_payloads.py`
Realistic payload generator with:
- Diurnal temperature cycles
- Soil moisture evaporation dynamics
- Correlated humidity patterns
- Battery drain simulation
- Random sensor failure/recovery events
- Rainfall and irrigation events

### `simulate_field.py`
End-to-end orchestrator that:
- Checks backend connectivity
- Generates payloads from multiple virtual nodes
- Sends to backend via HTTP POST
- Queries results to verify ingestion
- Prints summary report

## Example Output

```
  Sugarcane Field Simulation
  Backend: http://localhost:8000
  Nodes: 3
  Rounds: 5

--- Round 1/5 ---
  node-01 [ok]: soil_moisture=62.3, soil_temperature=28.1, ...
  node-02 [ok]: soil_moisture=71.5, soil_temperature=26.8, ...
  node-03 [degraded]: soil_moisture=55.2, humidity=0.0(invalid), ...

  Simulation Complete
  Total sent: 15
  Successful: 15
  Failed: 0

  Registered Nodes:
    node-01: 5 readings, last status=ok
    node-02: 5 readings, last status=ok
    node-03: 5 readings, last status=degraded
```
