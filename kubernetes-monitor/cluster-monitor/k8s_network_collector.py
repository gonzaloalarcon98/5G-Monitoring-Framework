"""
Kubernetes Pod Network Metrics Collector

This script retrieves network statistics (RX/TX bytes and packets) from pods 
within a specific namespace. It correlates internal interfaces with the Pod IP 
to ensure only relevant traffic is monitored.

Metrics are exported in Prometheus format for Node Exporter.
"""

import os
import time
import subprocess
import logging
from kubernetes import client, config

# Reusing the project's logging configuration
import config.logs as logger_setup

logger = logging.getLogger(logger_setup.__name__)

# --- Configuration ---
KUBECONFIG_PATH = "/home/gon/.kube/config"
NAMESPACE = "kube-system"
OUTPUT_FILE = "/var/lib/node-exporter/k8smetrics/network_metrics.prom"
POLLING_INTERVAL = 1  # seconds

def get_kube_client():
    """Initializes and returns the Kubernetes CoreV1 API client."""
    try:
        config.load_kube_config(config_file=KUBECONFIG_PATH)
        return client.CoreV1Api()
    except Exception as e:
        logger.error(f"Failed to load kubeconfig: {e}")
        return None

def exec_in_pod(pod_name, namespace, command):
    """Executes a command inside a specific pod using kubectl exec."""
    cmd = ['kubectl', 'exec', '-n', namespace, pod_name, '--'] + command
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        logger.warning(f"Cmd execution failed in {pod_name}: {result.stderr.strip()}")
        return None
    return result.stdout

def parse_network_data(link_output, addr_output, pod_ip, pod_name, namespace):
    """
    Parses 'ip -s link' and 'ip addr' output to correlate metrics with the Pod IP.
    """
    interface_ip_map = {}
    current_iface = None
    
    # Map interfaces to IPs
    for line in addr_output.splitlines():
        if ": " in line and "@" not in line:
            parts = line.split(": ")
            if len(parts) > 1:
                current_iface = parts[1].split()[0]
        elif "inet " in line and current_iface:
            ip = line.split()[1].split("/")[0]
            interface_ip_map[current_iface] = ip

    lines = link_output.splitlines()
    metrics = []
    iface = None
    rx_b = tx_b = rx_p = tx_p = 0

    # Parse statistics
    for i, line in enumerate(lines):
        if ": <" in line:
            # Save previous iface metrics if it matches Pod IP
            if iface and interface_ip_map.get(iface) == pod_ip:
                metrics.extend(format_prometheus(pod_name, namespace, iface, rx_b, tx_b, rx_p, tx_p))
            
            # Identify new interface
            iface = line.split(":")[1].split("<")[0].strip()
            rx_b = tx_b = rx_p = tx_p = 0

        if "RX:" in line and i + 1 < len(lines):
            stats = lines[i + 1].split()
            rx_b, rx_p = stats[0], stats[1]
        
        if "TX:" in line and i + 1 < len(lines):
            stats = lines[i + 1].split()
            tx_b, tx_p = stats[0], stats[1]

    # Final check for the last interface in the loop
    if iface and interface_ip_map.get(iface) == pod_ip:
        metrics.extend(format_prometheus(pod_name, namespace, iface, rx_b, tx_b, rx_p, tx_p))

    return metrics

def format_prometheus(pod, ns, iface, rx_b, tx_b, rx_p, tx_p):
    """Formats raw data into Prometheus gauge strings."""
    labels = f'pod="{pod}", namespace="{ns}", interface="{iface}"'
    return [
        f'pod_network_rx_bytes{{{labels}}} {rx_b}',
        f'pod_network_tx_bytes{{{labels}}} {tx_b}',
        f'pod_network_rx_packets{{{labels}}} {rx_p}',
        f'pod_network_tx_packets{{{labels}}} {tx_p}'
    ]

def collect_metrics(v1):
    """Iterates through pods and gathers network data."""
    try:
        pods = v1.list_namespaced_pod(namespace=NAMESPACE, watch=False)
    except Exception as e:
        logger.error(f"Error listing pods: {e}")
        return ""

    all_metrics = []
    for pod in pods.items:
        name = pod.metadata.name
        ip = pod.status.pod_ip
        
        if not ip:
            continue

        logger.debug(f"Collecting network data for {name} ({ip})")

        addr_out = exec_in_pod(name, NAMESPACE, ['ip', 'addr', 'show'])
        link_out = exec_in_pod(name, NAMESPACE, ['ip', '-s', 'link'])

        if addr_out and link_out:
            pod_metrics = parse_network_data(link_out, addr_out, ip, name, NAMESPACE)
            all_metrics.extend(pod_metrics)

    return "\n".join(all_metrics)

def main():
    """Main execution loop."""
    logger.info(f"Starting Network Collector for namespace: {NAMESPACE}")
    v1 = get_kube_client()
    
    if not v1:
        return

    while True:
        start_time = time.time()
        metrics_data = collect_metrics(v1)

        if metrics_data:
            try:
                # Use a temp file for atomic write
                temp_file = f"{OUTPUT_FILE}.tmp"
                with open(temp_file, "w") as f:
                    f.write(metrics_data + "\n")
                os.replace(temp_file, OUTPUT_FILE)
                logger.info(f"Metrics exported to {OUTPUT_FILE}")
            except Exception as e:
                logger.error(f"File write error: {e}")
        
        # Adjust sleep to maintain steady polling interval
        elapsed = time.time() - start_time
        time.sleep(max(0, POLLING_INTERVAL - elapsed))

if __name__ == '__main__':
    main()