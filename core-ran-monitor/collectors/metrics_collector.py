"""
Amarisoft WebSocket Metrics Collector

Asynchronous collector that retrieves stats and UE data 
from multiple LTE/5G network nodes using a unified connection logic.
"""

import asyncio
import websockets
import json
import logging
import time
import os
from configparser import ConfigParser
import config.logs as logs

# Configuration setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(BASE_DIR, 'config', 'config.ini')

parser = ConfigParser()
parser.read(config_path)

logger = logging.getLogger(logs.__name__)

async def fetch_node_metrics(q, section_name, node_type_label, address_key, port_key):
    """
    Generic asynchronous worker to collect metrics from any Amarisoft node.
    
    Args:
        q (Queue): Shared queue to store results.
        section_name (str): The [Section] in config.ini.
        node_type_label (str): Human-readable name for logging (e.g., 'CORE', 'T3').
        address_key (str): The IP key in the config (e.g., 'IP' or 'Callbox').
        port_key (str): The Port key in the config (e.g., 'ENB' or 'MME').
    """
    server_addr = f"{parser[section_name][address_key]}:{parser[section_name][port_key]}"
    limit = int(parser[section_name].get("request_limit", 20))
    interval = float(parser[section_name].get("request_interval", 10))
    
    logger.info(f"[{node_type_label}] Initiating connection to {server_addr}")
    
    request_count = 0
    while request_count < limit:
        try:
            async with websockets.connect(f"ws://{server_addr}", origin="Test", ping_interval=None) as ws:
                logger.info(f"[{node_type_label}] WebSocket established.")
                
                # Initial handshake
                raw_init = await ws.recv()
                msg_init = json.loads(raw_init)
                
                if not msg_init:
                    continue

                if msg_init.get("message") == "authenticate":
                    logger.warning(f"[{node_type_label}] Server requires authentication.")
                    return
                
                if msg_init.get("message") == "ready":
                    logger.info(f"[{node_type_label}] Node ready (Type: {msg_init.get('type')})")
                    
                    # Pre-defined payloads
                    payload_stats = {"message": "stats", "message_id": "5", "samples": True, "rf": True}
                    payload_ue = {"message": "ue_get", "message_id": "3", "stats": True}

                    while request_count < limit:
                        # 1. Fetch Stats
                        await ws.send(json.dumps(payload_stats))
                        resp_stats = json.loads(await ws.recv())
                        
                        # 2. Fetch UE Data
                        await ws.send(json.dumps(payload_ue))
                        resp_ue = json.loads(await ws.recv())
                        
                        logger.debug(f"[{node_type_label}] Data sampled ({request_count + 1}/{limit})")
                        
                        # Store results in the shared queue
                        q.put([resp_stats, resp_ue])
                        
                        # Wait for the next polling cycle
                        # Note: In a pure async app, we'd use await asyncio.sleep(interval)
                        # but we keep time.sleep to maintain compatibility with your threaded architecture
                        time.sleep(interval)
                        request_count += 1
                        
        except Exception as e:
            logger.error(f"[{node_type_label}] Connection error: {e}")
            # Optional: add a small delay before retry
            await asyncio.sleep(5) 
            return

async def callbox_connection(q):
    await fetch_node_metrics(q, "Amari", "Callbox", "Callbox", "ENB")

async def core_connection(q):
    await fetch_node_metrics(q, "CORE", "CORE-MME", "IP", "MME")

async def ran_connection(q):
    await fetch_node_metrics(q, "CORE", "CORE-RAN", "IP", "ENB")

async def t3_connection(q):
    await fetch_node_metrics(q, "FIUM_T3", "T3-RAN", "IP", "ENB")

async def pci503_connection(q):
    await fetch_node_metrics(q, "PCI_503", "PCI503-RAN", "IP", "ENB")

if __name__ == '__main__':
    # This block is for isolated testing purposes
    print("Script started in standalone mode. Use metricsToPrometheus.py to run the full stack.")