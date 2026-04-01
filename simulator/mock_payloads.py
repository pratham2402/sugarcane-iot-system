"""
Mock payload generator for end-to-end testing.

Generates realistic sugarcane field telemetry payloads that mimic
the output from ESP32 nodes. Includes:
- Realistic value ranges for sugarcane growing conditions
- Gradual value drift (not random jumps)
- Diurnal temperature/humidity patterns
- Occasional sensor failures
- Variable rainfall patterns
"""

import time
import random
import math
from typing import Dict, List, Optional


class FieldSimulator:
    """
    Simulates a sugarcane field with multiple sensor nodes.

    Each node has persistent state that evolves realistically over time,
    including diurnal temperature cycles and gradual soil moisture changes.
    """

    def __init__(self, node_count: int = 3):
        self.nodes: Dict[str, dict] = {}

        for i in range(1, node_count + 1):
            node_id = f"node-{i:02d}"
            self.nodes[node_id] = {
                "soil_moisture": random.uniform(50, 75),
                "soil_temperature": random.uniform(24, 30),
                "air_temperature": random.uniform(26, 34),
                "humidity": random.uniform(55, 85),
                "rainfall_total": 0,
                "flow_total": 0,
                "battery": random.uniform(3.6, 4.1),
                "sensor_health": {s: True for s in [
                    "sm", "st", "at", "hu", "rp", "fp"
                ]},
            }

    def generate_compact_payload(self, node_id: str) -> dict:
        """Generate a compact-format payload for a specific node."""
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node: {node_id}")

        state = self.nodes[node_id]
        self._evolve_state(state)

        readings = {}

        # Soil moisture
        if state["sensor_health"]["sm"]:
            readings["sm"] = [round(state["soil_moisture"], 1), True]
        else:
            readings["sm"] = [0.0, False]

        # Soil temperature
        if state["sensor_health"]["st"]:
            readings["st"] = [round(state["soil_temperature"], 1), True]
        else:
            readings["st"] = [0.0, False]

        # Air temperature
        if state["sensor_health"]["at"]:
            readings["at"] = [round(state["air_temperature"], 1), True]
        else:
            readings["at"] = [0.0, False]

        # Humidity
        if state["sensor_health"]["hu"]:
            readings["hu"] = [round(state["humidity"], 1), True]
        else:
            readings["hu"] = [0.0, False]

        # Rainfall (pulses since last reading)
        rain_pulses = random.randint(0, 3) if random.random() < 0.15 else 0
        state["rainfall_total"] += rain_pulses
        readings["rp"] = [rain_pulses, True]

        # Flow (pulses since last reading)
        flow_pulses = random.randint(5, 30) if random.random() < 0.25 else 0
        state["flow_total"] += flow_pulses
        readings["fp"] = [flow_pulses, True]

        # Determine status
        valid_count = sum(1 for v in readings.values() if v[1])
        total = len(readings)
        if valid_count == total:
            status = "ok"
        elif valid_count > 0:
            status = "degraded"
        else:
            status = "error"

        return {
            "n": node_id,
            "t": int(time.time()),
            "fw": "1.0.0",
            "bv": round(state["battery"], 2),
            "s": status,
            "r": readings,
        }

    def generate_full_payload(self, node_id: str) -> dict:
        """Generate a full-format payload (as stored/uploaded by gateway)."""
        compact = self.generate_compact_payload(node_id)

        reading_map = {
            "sm": ("soil_moisture", "%"),
            "st": ("soil_temperature", "°C"),
            "at": ("air_temperature", "°C"),
            "hu": ("humidity", "%"),
            "rp": ("rainfall_pulses", "pulses"),
            "fp": ("flow_pulses", "pulses"),
        }

        readings = {}
        for compact_key, (full_key, unit) in reading_map.items():
            if compact_key in compact["r"]:
                val, valid = compact["r"][compact_key]
                readings[full_key] = {
                    "value": val,
                    "unit": unit,
                    "valid": valid,
                }

        return {
            "node_id": compact["n"],
            "timestamp": compact["t"],
            "firmware_version": compact.get("fw"),
            "battery_voltage": compact.get("bv"),
            "status": compact["s"],
            "readings": readings,
        }

    def _evolve_state(self, state: dict) -> None:
        """Evolve sensor state with realistic drift patterns."""
        hour = time.localtime().tm_hour

        # Diurnal temperature cycle (warmer midday, cooler night)
        temp_bias = 3.0 * math.sin((hour - 6) * math.pi / 12)

        state["air_temperature"] = self._drift(
            state["air_temperature"] + temp_bias * 0.05,
            18, 44, 0.5
        )

        # Soil temp follows air with dampening and lag
        soil_target = state["air_temperature"] * 0.85 + 5
        state["soil_temperature"] += (soil_target - state["soil_temperature"]) * 0.1
        state["soil_temperature"] = max(15, min(45, state["soil_temperature"]))

        # Humidity inversely correlated with temperature
        hum_bias = -temp_bias * 2
        state["humidity"] = self._drift(
            state["humidity"] + hum_bias * 0.05,
            35, 98, 2.0
        )

        # Soil moisture slowly dries out, occasional "watering" events
        state["soil_moisture"] -= random.uniform(0.05, 0.3)  # Evaporation
        if random.random() < 0.02:  # 2% chance of irrigation/rain
            state["soil_moisture"] += random.uniform(10, 25)
        state["soil_moisture"] = max(20, min(95, state["soil_moisture"]))

        # Battery slowly drains
        state["battery"] -= random.uniform(0.0001, 0.001)
        state["battery"] = max(3.0, state["battery"])

        # Random sensor failures (rare)
        for sensor in state["sensor_health"]:
            if random.random() < 0.005:  # 0.5% failure rate per reading
                state["sensor_health"][sensor] = False
            elif random.random() < 0.05:  # 5% recovery rate
                state["sensor_health"][sensor] = True

    @staticmethod
    def _drift(current: float, min_v: float, max_v: float,
               step: float) -> float:
        """Apply random drift within bounds."""
        delta = random.uniform(-step, step)
        return max(min_v, min(max_v, current + delta))


def generate_batch(node_count: int = 3, readings_per_node: int = 1) -> List[dict]:
    """Generate a batch of full-format payloads."""
    sim = FieldSimulator(node_count)
    payloads = []

    for _ in range(readings_per_node):
        for node_id in sim.nodes:
            payloads.append(sim.generate_full_payload(node_id))
            time.sleep(0.01)  # Slightly different timestamps

    return payloads
