"""
Scenario Reset Utility

Resets all Prometheus metrics for vehicles and vOBU migrations by 
overwriting .prom files with Null/NaN values. Use this before 
starting a new simulation or test run.

"""

import os
import logging

# Reusing the project's logging configuration
import config.logs as logger_setup

logger = logging.getLogger(logger_setup.__name__)

# Constants for output paths
METRICS_DIR = "/var/lib/node-exporter/k8smetrics"
VEHICLE_PATH = os.path.join(METRICS_DIR, "vehiclePosition.prom")
VOBU_PATH = os.path.join(METRICS_DIR, "gpsTrackingPosition.prom")
DEFAULT_PLATE = "1311ABC"

def reset_metrics_file(filepath, content):
    """
    Overwrites a prometheus metrics file safely.
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        temp_path = f"{filepath}.tmp"
        with open(temp_path, "w") as f:
            f.write(content)
        os.replace(temp_path, filepath)
        logger.info(f"Successfully reset: {filepath}")
    except Exception as e:
        logger.error(f"Failed to reset {filepath}: {e}")

def get_vobu_reset_content():
    """Returns empty vOBU migration metrics content."""
    return (
        "# HELP vobu_active_latitude Latitude of the active vOBU instance.\n"
        "# TYPE vobu_active_latitude gauge\n"
        "vobu_active_latitude NaN\n"
        "vobu_active_longitude NaN\n"
        "# HELP vobu_migration_latitude Latitude of the migrating vOBU instance.\n"
        "# TYPE vobu_migration_latitude gauge\n"
        "vobu_migration_latitude NaN\n"
        "vobu_migration_longitude NaN\n"
        "# HELP vobu_cached_latitude Latitude of the cached/available vOBU instance.\n"
        "# TYPE vobu_cached_latitude gauge\n"
        "vobu_cached_latitude NaN\n"
        "vobu_cached_longitude NaN\n"
    )

def get_vehicle_reset_content(plate):
    """Returns empty vehicle GPS metrics content."""
    return (
        f"# HELP vehicle_latitude Latitude coordinate of the vehicle.\n"
        f"# TYPE vehicle_latitude gauge\n"
        f"vehicle_latitude{{plate=\"{plate}\"}} NaN\n"
        f"# HELP vehicle_longitude Longitude coordinate of the vehicle.\n"
        f"# TYPE vehicle_longitude gauge\n"
        f"vehicle_longitude{{plate=\"{plate}\"}} NaN\n"
    )

if __name__ == "__main__":
    print("--- Stage 0: Resetting Scenario Metrics ---")
    
    # Reset vOBU tracking
    vobu_content = get_vobu_reset_content()
    reset_metrics_file(VOBU_PATH, vobu_content)
    
    # Reset Vehicle tracking
    vehicle_content = get_vehicle_reset_content(DEFAULT_PLATE)
    reset_metrics_file(VEHICLE_PATH, vehicle_content)
    
    print("Scenario cleanup complete. Ready for new test run.")