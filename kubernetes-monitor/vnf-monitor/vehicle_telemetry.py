"""
Vehicle GPS Telemetry Collector

Retrieves real-time GPS coordinates from a central aggregator and exports 
them as Prometheus metrics for Node Exporter consumption.

"""

import requests
import time
import threading
import logging
import os
from configparser import ConfigParser

# Reusing your logging setup
import config.logs as logger_setup

logger = logging.getLogger(logger_setup.__name__)

# Constants for Fixed Cells (Ground Truth Reference)
FIXED_CELLS = {
    "ATICA": {"lat": 38.022561, "lon": -1.174164},
    "LUISVIVES": {"lat": 38.016011, "lon": -1.172289},
    "VITALIS": {"lat": 38.024773, "lon": -1.173043}
}

# Aggregator API Configuration
# Note: You could move these to config.ini for better flexibility
AGGREGATOR_URL = "http://10.208.11.21:8090/lastAttributeValue"
VEHICLE_PLATE = "1311ABC"
OUTPUT_PATH = "/var/lib/node-exporter/k8smetrics/vehiclePosition.prom"

# Global state
current_position = {"lat": None, "lon": None}

def fetch_vehicle_gps(plate, timeout=5):
    """
    Queries the GPS position from the telemetery aggregator.
    
    Returns:
        tuple: (latitude, longitude) if successful.
    """
    try:
        # Requesting Latitude and Longitude via GET parameters
        params_lat = {"vehicle": plate, "attribute": "LATITUDE,float"}
        params_lon = {"vehicle": plate, "attribute": "LONGITUDE,float"}

        resp_lat = requests.get(AGGREGATOR_URL, params=params_lat, timeout=timeout)
        resp_lon = requests.get(AGGREGATOR_URL, params=params_lon, timeout=timeout)

        if resp_lat.status_code == 200 and resp_lon.status_code == 200:
            lat = float(resp_lat.json()['value']['value'])
            lon = float(resp_lon.json()['value']['value'])
            return lat, lon
        
        logger.error(f"API Error: Lat Status {resp_lat.status_code}, Lon Status {resp_lon.status_code}")
        return None, None

    except requests.Timeout:
        logger.error("Timeout reached while connecting to Aggregator API.")
    except Exception as e:
        logger.error(f"Unexpected error fetching GPS data: {e}")
    
    return None, None

def export_to_prometheus(plate, lat, lon, filepath):
    """
    Writes GPS data in Prometheus Text Format to a .prom file.
    """
    if lat is None or lon is None:
        return

    content = (
        f"# HELP vehicle_latitude Latitude coordinate of the vehicle.\n"
        f"# TYPE vehicle_latitude gauge\n"
        f"vehicle_latitude{{plate=\"{plate}\"}} {lat}\n"
        f"# HELP vehicle_longitude Longitude coordinate of the vehicle.\n"
        f"# TYPE vehicle_longitude gauge\n"
        f"vehicle_longitude{{plate=\"{plate}\"}} {lon}\n"
    )

    try:
        # Using a temporary file and renaming it is a best practice to avoid partial reads
        temp_file = f"{filepath}.tmp"
        with open(temp_file, "w") as f:
            f.write(content)
        os.replace(temp_file, filepath)
        logger.debug(f"Telemetry exported to {filepath}")
    except Exception as e:
        logger.error(f"Failed to write Prometheus file: {e}")

def run_telemetry_loop(plate, output_file, interval=1):
    """
    Background worker that updates GPS data periodically.
    """
    global current_position
    logger.info(f"Starting GPS update loop for vehicle {plate} every {interval}s.")
    
    while True:
        lat, lon = fetch_vehicle_gps(plate)
        
        if lat and lon:
            current_position["lat"], current_position["lon"] = lat, lon
            export_to_prometheus(plate, lat, lon, output_file)
        
        time.sleep(interval)

if __name__ == "__main__":
    # Standard script execution
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        
        # Start telemetry thread
        telemetry_thread = threading.Thread(
            target=run_telemetry_loop, 
            args=(VEHICLE_PLATE, OUTPUT_PATH, 1),
            daemon=True
        )
        telemetry_thread.start()

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Telemetry collector stopped by user.")