"""
vOBU Migration Tracker

Monitors virtual On-Board Units (vOBUs) status and location.
It tracks if a service is ACTIVE (Busy), MIGRATING, or CACHED (Available)
based on their serving cells and exports the data for Prometheus.

"""

import requests
import time
import logging
import os

# Reusing the project's logging configuration
import config.logs as logger_setup

logger = logging.getLogger(logger_setup.__name__)

# Fixed Cell Coordinates (Reference Data)
CELL_COORDS = {
    "ATICA": (38.022561, -1.174164),
    "LUIS VIVES": (38.016011, -1.172289),
    "VITALIS": (38.024773, -1.173043)
}

# API Configuration
MANAGER_BASE_URL = "http://10.208.11.21:8070"
VEHICLE_PLATE = "1311ABC"
OUTPUT_METRICS_PATH = "/var/lib/node-exporter/k8smetrics/gpsTrackingPosition.prom"

def get_vobu_ips(plate, timeout=5):
    """
    Retrieves the IP addresses for the primary and secondary vOBUs.
    """
    url = f"{MANAGER_BASE_URL}/getVobuList"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        primary_ip = None
        secondary_ip = None

        for vobu in data:
            if vobu.get("plate") == plate:
                primary_ip = vobu.get("ip")
            else:
                secondary_ip = vobu.get("ip")

        if not primary_ip or not secondary_ip:
            logger.error(f"Could not identify both vOBUs for plate {plate}")
            return None, None

        return primary_ip, secondary_ip

    except Exception as e:
        logger.error(f"Failed to retrieve vOBU list: {e}")
        return None, None

def get_vobu_status(ip, timeout=5):
    """
    Queries the specific status and serving cell of a vOBU by its IP.
    """
    url = f"{MANAGER_BASE_URL}/getVobuStatus"
    params = {"vobu": ip}
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK":
            val = data.get('value', {})
            return val.get('status'), val.get('serving_cell')
        
        logger.warning(f"Non-OK status for vOBU {ip}: {data.get('status')}")
        return None, None

    except Exception as e:
        logger.error(f"Error querying vOBU {ip}: {e}")
        return None, None

def export_vobu_metrics(plate, data_map, filepath):
    """
    Exports the migration and status metrics in Prometheus text format.
    """
    def fmt(val): return val if val is not None else 'NaN'

    content = (
        f"# HELP vobu_active_latitude Latitude of the active vOBU instance.\n"
        f"# TYPE vobu_active_latitude gauge\n"
        f"vobu_active_latitude {fmt(data_map['active_lat'])}\n"
        f"vobu_active_longitude {fmt(data_map['active_lon'])}\n"
        
        f"# HELP vobu_migration_latitude Latitude of the migrating vOBU instance.\n"
        f"# TYPE vobu_migration_latitude gauge\n"
        f"vobu_migration_latitude {fmt(data_map['migrating_lat'])}\n"
        f"vobu_migration_longitude {fmt(data_map['migrating_lon'])}\n"
        
        f"# HELP vobu_cached_latitude Latitude of the cached/available vOBU instance.\n"
        f"# TYPE vobu_cached_latitude gauge\n"
        f"vobu_cached_latitude {fmt(data_map['cached_lat'])}\n"
        f"vobu_cached_longitude {fmt(data_map['cached_lon'])}\n"
    )

    try:
        temp_path = f"{filepath}.tmp"
        with open(temp_path, "w") as f:
            f.write(content)
        os.replace(temp_path, filepath)
        logger.debug("Migration metrics updated.")
    except Exception as e:
        logger.error(f"Failed to write metrics file: {e}")

def run_migration_tracker():
    """Main loop to track vOBU status and cell location."""
    logger.info("Initializing vOBU Migration Tracker...")
    
    primary_ip, secondary_ip = get_vobu_ips(VEHICLE_PLATE)
    if not primary_ip:
        logger.critical("Primary vOBU IP not found. Exiting.")
        return

    while True:
        try:
            metrics = {
                'active_lat': None, 'active_lon': None,
                'migrating_lat': None, 'migrating_lon': None,
                'cached_lat': None, 'cached_lon': None
            }

            for ip in [primary_ip, secondary_ip]:
                status, cell = get_vobu_status(ip)
                
                if not status or cell not in CELL_COORDS:
                    continue

                lat, lon = CELL_COORDS[cell]

                # Mapping statuses to metric categories
                if status == "BUSY":
                    metrics['active_lat'], metrics['active_lon'] = lat, lon
                elif status == "MIGRATING":
                    metrics['migrating_lat'], metrics['migrating_lon'] = lat, lon
                elif status in ["AVAILABLE", "CACHED"]:
                    metrics['cached_lat'], metrics['cached_lon'] = lat, lon

            export_vobu_metrics(VEHICLE_PLATE, metrics, OUTPUT_METRICS_PATH)
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Tracker stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected loop error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_migration_tracker()