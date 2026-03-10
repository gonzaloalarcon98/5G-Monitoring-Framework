"""
CPU Energy Consumption Estimator

Calculates estimated power consumption (in Watts) by correlating CPU load
with the system's Thermal Design Power (TDP). 

Formula: Estimated Power = (Total CPU % / 100) * TDP
"""

import subprocess
import time
import re
import socket
import logging
import os

# Reusing the project's logging configuration
import config.logs as logger_setup

logger = logging.getLogger(logger_setup.__name__)

# --- Configuration ---
TDP_WATTS = 65.0
OUTPUT_FILE = "/var/lib/node-exporter/k8smetrics/energy_metrics.prom"
POLLING_INTERVAL = 1  # seconds

def get_node_details():
    """
    Dynamically retrieves the node's hostname and primary IP address.
    """
    try:
        hostname = socket.gethostname()
        # Get primary IP by connecting to an external address (doesn't send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_addr = s.getsockname()[0]
        s.close()
        return hostname, ip_addr
    except Exception as e:
        logger.warning(f"Could not detect node details automatically: {e}")
        return "unknown-node", "0.0.0.0"

def get_cpu_stats():
    """Executes pidstat to gather CPU usage statistics over 5 samples."""
    cmd = ["pidstat", "-u", "1", "5"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute pidstat: {e.stderr}")
        return None

def calculate_power_usage(raw_output, node_name, node_ip):
    """
    Parses pidstat output and estimates energy consumption.
    """
    total_cpu_load = 0.0
    lines = raw_output.splitlines()
    
    # Regex to match pidstat output format (Average/Timestamp, UID, PID, %usr, %system, etc.)
    # We target the %CPU column (usually the last numeric group)
    pattern = re.compile(r"^\d{2}:\d{2}:\d{2}\s+\w+\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)")

    for line in lines:
        match = pattern.match(line)
        if match:
            try:
                total_cpu_load += float(match.group(1))
            except ValueError:
                continue

    if total_cpu_load > 0:
        # Estimation formula based on TDP
        estimated_watts = (total_cpu_load / 100) * TDP_WATTS
        
        # Prepare Prometheus Metrics
        labels = f'node="{node_name}", ip="{node_ip}"'
        metrics = [
            f'# HELP cpu_total_energy_watts Estimated power consumption in Watts based on CPU load and TDP.',
            f'# TYPE cpu_total_energy_watts gauge',
            f'cpu_total_energy_watts{{{labels}}} {estimated_watts}'
        ]
        return "\n".join(metrics)
    
    return None

def main():
    """Main execution loop for energy metrics collection."""
    node_name, node_ip = get_node_details()
    logger.info(f"Energy Collector started for {node_name} ({node_ip}) with TDP={TDP_WATTS}W")

    while True:
        start_time = time.time()
        
        cpu_data = get_cpu_stats()
        if cpu_data:
            prometheus_data = calculate_power_usage(cpu_data, node_name, node_ip)

            if prometheus_data:
                try:
                    # Atomic write using temporary file
                    temp_file = f"{OUTPUT_FILE}.tmp"
                    with open(temp_file, "w") as f:
                        f.write(prometheus_data + "\n")
                    os.replace(temp_file, OUTPUT_FILE)
                    logger.debug(f"Energy metrics updated: {prometheus_data.splitlines()[-1]}")
                except Exception as e:
                    logger.error(f"Failed to write energy metrics: {e}")
        
        # Adjust sleep to maintain steady polling interval
        elapsed = time.time() - start_time
        time.sleep(max(0, POLLING_INTERVAL - elapsed))

if __name__ == '__main__':
    main()