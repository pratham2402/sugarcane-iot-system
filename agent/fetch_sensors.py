"""
fetch_sensors.py — Reads the latest sensor data from the Pi backend.
"""

import requests

BACKEND_URL = "http://localhost:8000"

def fetch_latest_readings():
    """Fetch the most recent reading from each node."""
    url = f"{BACKEND_URL}/latest-readings"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def main():
    print("Fetching latest sensor readings...\n")

    try:
        data = fetch_latest_readings()
    except requests.RequestException as e:
        print(f"ERROR: Could not reach backend: {e}")
        print("Is the backend running on port 8000?")
        return

    # The backend returns a list of nodes
    nodes = data.get("nodes", [])

    if not nodes:
        print("No nodes found. Is the ESP32 sending data?")
        return

    for node in nodes:
        node_id = node.get("node_id", "unknown")
        firmware = node.get("firmware_version", "?")
        timestamp = node.get("timestamp", "?")
        status = node.get("status", "?")

        print(f"Node: {node_id}")
        print(f"  Firmware:    {firmware}")
        print(f"  Timestamp:   {timestamp}")
        print(f"  Status:      {status}")
        print(f"  Soil moisture:    {node.get('soil_moisture', '?')} %")
        print(f"  Soil temperature: {node.get('soil_temperature', '?')} °C")
        print(f"  Air temperature:  {node.get('air_temperature', '?')} °C")
        print(f"  Humidity:         {node.get('humidity', '?')} %")
        print()

    print("✅ Sensor data fetched successfully!")


if __name__ == "__main__":
    main()
