"""
Gateway main entry point.

Orchestrates all gateway subsystems:
1. Loads configuration
2. Initializes database
3. Starts receiver (LoRa or Mock)
4. Starts upload worker
5. Runs main receive → parse → store → queue loop
"""

import os
import sys
import json
import time
import signal
import logging
import argparse

import yaml

from .receiver.base_receiver import BaseReceiver
from .receiver.mock_receiver import MockReceiver
from .parser.telemetry_parser import TelemetryParser
from .storage.migrations import initialize_database
from .storage.database import GatewayDatabase
from .uploader.cloud_uploader import CloudUploader
from .uploader.retry_queue import RetryQueueWorker
from .health.monitor import HealthMonitor
from .utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    logger.info(f"Configuration loaded from {config_path}")
    return config


def create_receiver(config: dict) -> BaseReceiver:
    """Create the appropriate receiver based on configuration."""
    receiver_type = config.get("receiver", {}).get("type", "mock")

    if receiver_type == "lora":
        try:
            from .receiver.lora_receiver import LoRaReceiver
            return LoRaReceiver(config["receiver"]["lora"])
        except ImportError:
            logger.warning("LoRa dependencies not available, falling back to mock")
            return MockReceiver(config.get("receiver", {}).get("mock", {}))
    else:
        return MockReceiver(config.get("receiver", {}).get("mock", {}))


def main():
    """Gateway main function."""
    parser = argparse.ArgumentParser(
        description="Sugarcane Field Gateway — Telemetry Aggregator"
    )
    parser.add_argument(
        "--config", "-c",
        default="config/gateway_config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Force mock receiver mode"
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Override receiver type if --mock flag is set
    if args.mock:
        config.setdefault("receiver", {})["type"] = "mock"

    # Setup logging
    gw_config = config.get("gateway", {})
    setup_logging(
        log_level=gw_config.get("log_level", "INFO"),
        log_file=gw_config.get("log_file", "logs/gateway.log")
    )

    logger.info("=" * 60)
    logger.info("  Sugarcane Field Gateway Starting")
    logger.info(f"  Gateway ID: {gw_config.get('id', 'unknown')}")
    logger.info(f"  Name: {gw_config.get('name', 'unnamed')}")
    logger.info("=" * 60)

    # Initialize database
    db_path = config.get("storage", {}).get("database_path", "data/gateway.db")
    conn = initialize_database(db_path)
    db = GatewayDatabase(conn)
    logger.info(f"Database ready: {db.get_reading_count()} existing readings")

    # Initialize subsystems
    receiver = create_receiver(config)
    telemetry_parser = TelemetryParser()
    uploader = CloudUploader(config.get("cloud", {}))
    upload_worker = RetryQueueWorker(db, uploader, config.get("cloud", {}))
    health_monitor = HealthMonitor(config.get("health", {}))

    # Start subsystems
    receiver.start()
    upload_worker.start()

    # Setup graceful shutdown
    shutdown = False

    def signal_handler(sig, frame):
        nonlocal shutdown
        logger.info("Shutdown signal received")
        shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ─── Main Loop ────────────────────────────────────────────────────────────

    logger.info("Entering main receive loop")
    health_check_interval = config.get("health", {}).get("check_interval", 60)
    last_health_check = 0

    try:
        while not shutdown:
            # Attempt to receive a packet
            packet = receiver.receive()

            if packet is not None:
                health_monitor.record_packet_received()
                logger.info(
                    f"Received packet: {len(packet.data)} bytes "
                    f"(RSSI={packet.rssi}, source={packet.source})"
                )

                # Store raw packet
                db.store_raw_packet(packet)

                # Parse and validate
                record = telemetry_parser.parse(packet.data)

                if record is not None:
                    health_monitor.record_packet_parsed(True)
                    logger.info(
                        f"Parsed: node={record.node_id}, "
                        f"status={record.status}, "
                        f"readings={len(record.readings)}"
                    )

                    # Store parsed telemetry
                    telemetry_id = db.store_telemetry(record)

                    if telemetry_id is not None:
                        # Enqueue for cloud upload
                        db.enqueue_for_upload(telemetry_id, record)
                        logger.debug(f"Queued for upload: telemetry_id={telemetry_id}")
                else:
                    health_monitor.record_packet_parsed(False)
                    logger.warning("Failed to parse packet")

            # Periodic health check
            now = time.time()
            if (now - last_health_check) > health_check_interval:
                last_health_check = now
                status = health_monitor.get_status(
                    receiver, db, uploader, upload_worker
                )
                logger.info(
                    f"Health: {status['status']} | "
                    f"Packets: {status['packets']['received']} recv, "
                    f"{status['packets']['parsed']} parsed | "
                    f"Queue: {status['upload']['queue'].get('pending', 0)} pending | "
                    f"Nodes: {status['nodes']['registered']}"
                )

    except Exception as e:
        logger.error(f"Main loop error: {e}", exc_info=True)

    finally:
        # Graceful shutdown
        logger.info("Shutting down...")
        upload_worker.stop()
        receiver.stop()
        conn.close()
        logger.info("Gateway stopped cleanly")


if __name__ == "__main__":
    main()
