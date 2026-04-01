#!/usr/bin/env python3
"""
ESP32 Simulator — sends mock telemetry packets to the gateway.

This script generates realistic ESP32 telemetry payloads and sends them
to the gateway's receiver via stdout (for serial transport) or directly
by importing the gateway modules.

Usage:
    python scripts/simulate_esp32.py --nodes 3 --interval 5 --count 10
"""

import json
import time
import random
import argparse
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_compact_payload(node_id: str, state: dict) -> str:
    """Generate a compact telemetry payload matching ESP32 output format."""

    # Drift sensor values
    state["sm"] = drift(state.get("sm", 60), 35, 90, 2.0)
    state["st"] = drift(state.get("st", 27), 18, 42, 0.5)
    state["at"] = drift(state.get("at", 30), 20, 44, 0.8)
    state["hu"] = drift(state.get("hu", 70), 40, 98, 3.0)
    state["rp"] = state.get("rp", 0) + (random.randint(0, 2) if random.random() < 0.15 else 0)
    state["fp"] = state.get("fp", 0) + (random.randint(0, 15) if random.random() < 0.3 else 0)

    readings = {
        "sm": [round(state["sm"], 1), random.random() > 0.03],
        "st": [round(state["st"], 1), random.random() > 0.03],
        "at": [round(state["at"], 1), random.random() > 0.03],
        "hu": [round(state["hu"], 1), random.random() > 0.03],
        "rp": [state["rp"], True],
        "fp": [state["fp"], True],
    }

    valid_count = sum(1 for v in readings.values() if v[1])
    status = "ok" if valid_count == len(readings) else (
        "degraded" if valid_count > 0 else "error"
    )

    payload = {
        "n": node_id,
        "t": int(time.time()),
        "fw": "1.0.0",
        "bv": round(random.uniform(3.4, 4.1), 2),
        "s": status,
        "r": readings,
    }

    return json.dumps(payload, separators=(",", ":"))


def drift(current: float, min_v: float, max_v: float, step: float) -> float:
    """Apply random drift within bounds."""
    return max(min_v, min(max_v, current + random.uniform(-step, step)))


def main():
    parser = argparse.ArgumentParser(description="ESP32 Telemetry Simulator")
    parser.add_argument("--nodes", type=int, default=3, help="Number of simulated nodes")
    parser.add_argument("--interval", type=float, default=5, help="Seconds between packets")
    parser.add_argument("--count", type=int, default=0, help="Total packets (0=infinite)")
    args = parser.parse_args()

    print(f"Simulating {args.nodes} ESP32 nodes, interval={args.interval}s")

    # Per-node state
    states = {}
    for i in range(1, args.nodes + 1):
        states[f"node-{i:02d}"] = {}

    sent = 0
    node_ids = list(states.keys())

    try:
        while args.count == 0 or sent < args.count:
            node_id = node_ids[sent % len(node_ids)]
            payload = generate_compact_payload(node_id, states[node_id])

            print(f"<<PKT>>")
            print(payload)
            print(f"<</PKT>>")
            sys.stdout.flush()

            sent += 1
            print(f"[SIM] Sent packet #{sent} from {node_id} ({len(payload)} bytes)",
                  file=sys.stderr)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n[SIM] Stopped after {sent} packets", file=sys.stderr)


if __name__ == "__main__":
    main()
