"""
Prometheus Metrics Exporter for Amarisoft Nodes

This script orchestrates the collection of telemetry data from multiple nodes
and exposes them via an HTTP endpoint for Prometheus scraping.
"""

import time
import asyncio
import logging
import threading
import queue
import signal
import sys
from prometheus_client import start_http_server, Gauge
from configparser import ConfigParser
import os

# Project modules
import config.logs as logs
import collectors.metrics_collector as metrics_collector
import collectors.imsi_manager as imsi_manager
from ue import UE

# Logger and Thread Safety
logger = logging.getLogger(logs.__name__)
lock = threading.Lock()

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(BASE_DIR, 'config', 'config.ini')

parser = ConfigParser()
parser.read(config_path)

# Global storage for Prometheus Gauges
prometheus_metrics = {}

def interrupt_handler(signum, frame):
    """Graceful shutdown handler."""
    logger.info(f'Signal {signum} received. Saving data and exiting...')
    imsi_manager.save_imsis()
    sys.exit(0)

def process_dictionary(data_dict, prefix):
    """Recursively maps dictionary keys to Prometheus Gauges."""
    for key, value in data_dict.items():
        metric_name = f"{prefix}_{key}"
        
        if isinstance(value, list):
            process_list(value, metric_name)
        elif isinstance(value, dict):
            process_dictionary(value, metric_name)
        elif not isinstance(value, str):
            if metric_name not in prometheus_metrics:
                prometheus_metrics[metric_name] = Gauge(metric_name, f"Metric: {key}")
            prometheus_metrics[metric_name].set(value)

def process_list(data_list, prefix):
    """Processes lists, handling special cases for UE identification via IMSI."""
    for index, item in enumerate(data_list):
        if isinstance(item, dict):
            # Attempt to map UE IDs to IMSI for meaningful metric names
            if "ran_ue_id" in item and "amf_ue_id" in item:
                with lock:
                    try:
                        temp_ue = UE(item["ran_ue_id"], item['amf_ue_id'], None)
                        if temp_ue in imsi_manager.ueList:
                            imsi = imsi_manager.ueList[imsi_manager.ueList.index(temp_ue)].imsi
                            process_dictionary(item, f"{prefix}_{imsi}")
                            continue
                    except Exception:
                        pass
            process_dictionary(item, f"{prefix}_{index}")
        elif isinstance(item, list):
            process_list(item, f"{prefix}_{index}")

def sanitize_values(data):
    """Converts numeric strings to types and strips quotes."""
    if isinstance(data, dict):
        return {k: sanitize_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_values(i) for i in data]
    try:
        return int(data)
    except (ValueError, TypeError):
        try:
            return float(data)
        except (ValueError, TypeError):
            return str(data).strip("'")

def load_metrics():
    """Main execution loop for metric collection threads."""
    # Read the limit once per cycle to allow dynamic config updates if the loop restarts
    request_limit = int(parser["Amari"].get("request_limit", 20))
    
    while True:
        try:
            # Queues for data exchange
            que_server = queue.Queue()
            que_core = queue.Queue()

            # Starting collector threads
            # Notice we no longer need to pass 'server_address' as an argument!
            threads = [
                threading.Thread(target=asyncio.run, args=(metrics_collector.callbox_connection(que_server),), daemon=True),
                threading.Thread(target=asyncio.run, args=(metrics_collector.core_connection(que_core),), daemon=True)
            ]

            for t in threads:
                t.start()

            for i in range(request_limit):
                # Pull data from nodes
                server_data = que_server.get(block=True)
                core_data = que_core.get(block=True)

                # Process Node Stats (index 0 of the list sent by metrics_collector)
                process_dictionary(server_data[0], "amari_gnb")
                process_dictionary(core_data[0], "core_gnb")

                # Process UE Data (index 1 of the list)
                process_dictionary(server_data[1], "amari_ue")
                core_ue_clean = sanitize_values(core_data[1])
                process_dictionary(core_ue_clean, "core_ue")

                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] Update {i+1}/{request_limit}: Metrics pushed to Prometheus")
                logger.debug("Metrics cycle updated successfully.")

            for t in threads:
                t.join()

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupt_handler)
    signal.signal(signal.SIGINT, interrupt_handler)

    port = int(parser['Prometheus'].get('port', 8082))
    start_http_server(port)
    logger.info(f"Exporter running on port {port}")

    load_metrics()