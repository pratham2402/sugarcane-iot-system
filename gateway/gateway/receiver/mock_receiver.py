"""
Mock receiver for development and testing.

Generates realistic simulated telemetry packets at configurable intervals.
Mimics the behavior of real ESP32 field nodes with varying sensor values,
occasional failures, and realistic data distributions.
"""

import json
import time
import random
import logging
from typing import Optional

from .base_receiver import BaseReceiver, RawPacket

logger = logging.getLogger(__name__)


class MockReceiver(BaseReceiver):
    """
    Simulated packet receiver that generates realistic field telemetry.

    Produces packets from multiple virtual nodes with:
    - Realistic sugarcane field sensor value ranges
    - Gradual value drift (not random jumps)
    - Occasional sensor failures
    - Configurable node count and interval
    """

    def __init__(self, config: dict):
        self.config = config
        self._active = False
        self._interval = config.get("interval", 5)
        self._node_count = config.get("node_count", 3)
        self._last_packet_time = 0.0
        self._current_node_index = 0

        # Simulated state per node (for value drift)
        self._node_states = {}
        for i in range(1, self._node_count + 1):
            node_id = f"node-{i:02d}"
            self._node_states[node_id] = {
                "soil_moisture": random.uniform(45, 75),
                "soil_temperature": random.uniform(24, 32),
                "air_temperature": random.uniform(26, 36),
                "humidity": random.uniform(55, 85),
                "rainfall_pulses": 0,
                "flow_pulses": 0,
            }

    def start(self) -> None:
        self._active = True
        self._last_packet_time = time.time()
        logger.info(
            f"Mock receiver started: {self._node_count} nodes, "
            f"{self._interval}s interval"
        )

    def receive(self) -> Optional[RawPacket]:
        if not self._active:
            return None

        now = time.time()
        if (now - self._last_packet_time) < self._interval:
            time.sleep(0.1)  # Avoid busy-waiting
            return None

        self._last_packet_time = now

        # Cycle through nodes
        node_index = (self._current_node_index % self._node_count) + 1
        self._current_node_index += 1
        node_id = f"node-{node_index:02d}"

        # Generate payload
        payload = self._generate_payload(node_id)
        payload_str = json.dumps(payload, separators=(",", ":"))

        packet = RawPacket(
            data=payload_str,
            received_at=now,
            rssi=random.uniform(-90, -40),
            snr=random.uniform(5, 15),
            source="mock"
        )

        logger.debug(f"Mock packet from {node_id}: {len(payload_str)} bytes")
        return packet

    def stop(self) -> None:
        self._active = False
        logger.info("Mock receiver stopped")

    def is_active(self) -> bool:
        return self._active

    def _generate_payload(self, node_id: str) -> dict:
        """Generate a compact telemetry payload with realistic drift."""
        state = self._node_states[node_id]

        # Apply small random drift to each value
        state["soil_moisture"] = self._drift(state["soil_moisture"], 40, 85, 2.0)
        state["soil_temperature"] = self._drift(state["soil_temperature"], 20, 40, 0.5)
        state["air_temperature"] = self._drift(state["air_temperature"], 22, 42, 0.8)
        state["humidity"] = self._drift(state["humidity"], 45, 95, 3.0)

        # Pulse counters accumulate
        if random.random() < 0.1:  # 10% chance of rain tip
            state["rainfall_pulses"] += random.randint(1, 3)
        if random.random() < 0.3:  # 30% chance of flow
            state["flow_pulses"] += random.randint(5, 20)

        # Simulate occasional sensor failure (5% chance per reading)
        readings = {}

        for key, compact_key in [
            ("soil_moisture", "sm"),
            ("soil_temperature", "st"),
            ("air_temperature", "at"),
            ("humidity", "hu"),
            ("rainfall_pulses", "rp"),
            ("flow_pulses", "fp"),
        ]:
            # Not every node has every sensor — skip some randomly on init
            # but keep it consistent per node
            value = state[key]
            valid = random.random() > 0.05  # 5% failure rate
            if isinstance(value, float):
                readings[compact_key] = [round(value, 1), valid]
            else:
                readings[compact_key] = [int(value), valid]

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
            "bv": round(random.uniform(3.3, 4.2), 2),
            "s": status,
            "r": readings,
        }

    @staticmethod
    def _drift(current: float, min_val: float, max_val: float,
               max_step: float) -> float:
        """Apply a small random drift to a value, clamped to range."""
        delta = random.uniform(-max_step, max_step)
        new_val = current + delta
        return max(min_val, min(max_val, new_val))
