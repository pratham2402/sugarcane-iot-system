#!/usr/bin/env python3
"""
End-to-end field simulation.

Simulates the complete data pipeline:
1. Generates mock ESP32 telemetry (as if nodes are in the field)
2. Sends payloads directly to the cloud backend API
3. Verifies data appears correctly via query endpoints

This validates the end-to-end architecture without any hardware.

Usage:
    # Start the backend first:
    #   cd backend && python -m app.main
    #
    # Then run the simulation:
    python simulate_field.py
    python simulate_field.py --url http://localhost:8000 --nodes 5 --rounds 10
"""

import json
import time
import argparse
import logging
import sys

import requests

from mock_payloads import FieldSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
)
logger = logging.getLogger(__name__)


def check_backend(base_url: str) -> bool:
    """Check if the backend is running."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                f"Backend OK: {data.get('total_readings', 0)} readings, "
                f"{data.get('total_nodes', 0)} nodes"
            )
            return True
    except requests.ConnectionError:
        pass

    logger.error(f"Backend not reachable at {base_url}")
    return False


def send_telemetry(base_url: str, payload: dict) -> bool:
    """Send a single telemetry payload to the backend."""
    try:
        resp = requests.post(
            f"{base_url}/telemetry/ingest",
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        else:
            logger.warning(f"Ingest failed: {resp.status_code} {resp.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return False


def query_latest(base_url: str) -> dict:
    """Query latest readings from the backend."""
    try:
        resp = requests.get(f"{base_url}/latest-readings", timeout=5)
        return resp.json()
    except requests.RequestException:
        return {}


def query_nodes(base_url: str) -> list:
    """Query registered nodes."""
    try:
        resp = requests.get(f"{base_url}/nodes", timeout=5)
        return resp.json()
    except requests.RequestException:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end field simulation for the sugarcane monitoring system"
    )
    parser.add_argument(
        "--url", default="http://localhost:8000",
        help="Backend API URL"
    )
    parser.add_argument(
        "--nodes", type=int, default=3,
        help="Number of simulated field nodes"
    )
    parser.add_argument(
        "--rounds", type=int, default=10,
        help="Number of simulation rounds"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Seconds between rounds"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  Sugarcane Field Simulation")
    logger.info(f"  Backend: {args.url}")
    logger.info(f"  Nodes: {args.nodes}")
    logger.info(f"  Rounds: {args.rounds}")
    logger.info("=" * 60)

    # Check backend
    if not check_backend(args.url):
        logger.error("Cannot proceed without a running backend.")
        logger.error("Start the backend: cd backend && python -m app.main")
        sys.exit(1)

    # Create simulator
    sim = FieldSimulator(args.nodes)
    node_ids = list(sim.nodes.keys())

    total_sent = 0
    total_ok = 0
    total_failed = 0

    try:
        for round_num in range(1, args.rounds + 1):
            logger.info(f"\n--- Round {round_num}/{args.rounds} ---")

            for node_id in node_ids:
                payload = sim.generate_full_payload(node_id)

                # Show summary
                readings_summary = ", ".join(
                    f"{k}={v['value']}"
                    for k, v in payload["readings"].items()
                    if v.get("valid", False)
                )

                logger.info(
                    f"  {node_id} [{payload['status']}]: {readings_summary}"
                )

                # Send to backend
                if send_telemetry(args.url, payload):
                    total_ok += 1
                else:
                    total_failed += 1
                total_sent += 1

            # Pause between rounds
            if round_num < args.rounds:
                time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("\nSimulation interrupted by user")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("  Simulation Complete")
    logger.info(f"  Total sent: {total_sent}")
    logger.info(f"  Successful: {total_ok}")
    logger.info(f"  Failed: {total_failed}")
    logger.info("=" * 60)

    # Query final state
    logger.info("\n  Registered Nodes:")
    nodes = query_nodes(args.url)
    for node in nodes:
        logger.info(
            f"    {node['node_id']}: "
            f"{node.get('total_readings', 0)} readings, "
            f"last status={node.get('last_status', '?')}"
        )

    logger.info("\n  Latest Readings:")
    latest = query_latest(args.url)
    for node_data in latest.get("nodes", []):
        sm = node_data.get("soil_moisture", "—")
        at = node_data.get("air_temperature", "—")
        hu = node_data.get("humidity", "—")
        logger.info(
            f"    {node_data['node_id']}: "
            f"moisture={sm}%, temp={at}°C, humidity={hu}%"
        )

    # Health check
    health = check_backend(args.url)
    logger.info(f"\n  Backend health: {'OK' if health else 'FAIL'}")


if __name__ == "__main__":
    main()
