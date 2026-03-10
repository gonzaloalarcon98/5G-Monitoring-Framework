# 5G-Monitoring-Framework

A comprehensive telemetry and analytics suite for hybrid 5G environments. This framework provides real-time monitoring for Amarisoft 5G/LTE stacks and Kubernetes-based Virtual Network Functions (VNFs), exporting data directly to Prometheus for visualization in Grafana.



## Repository Structure

The project is organized into two main specialized modules:

### 1. Core-RAN Monitor

Focuses on the physical and protocol layers of the 5G stack.

- **`collectors/`**: Handles WebSocket connections to Amarisoft nodes.
- **`config/`**: Centralized configuration and professional logging setup.
- **`exporter/`**: The main Prometheus HTTP Exporter.

### 2. Kubernetes Monitor

Focuses on the virtualization and application layers.

- **`cluster-monitor/`**: Monitors node energy and Pod network statistics.
- **`vnf-monitor/`**: Tracks vehicle GPS telemetry and vOBU (Virtual On-Board Unit) service migrations.



## Getting Started

### Prerequisites

- **Python 3.9+**
- **Kubernetes Cluster** with `kubectl` access.
- **Prometheus Node Exporter** (with `--collector.textfile.directory` enabled).
- **Amarisoft Software Suite** (Callbox or separate Core/RAN nodes).

### Installation

1. Clone the repository:

   Bash

   ```
   git clone https://github.com/gonzaloalarcon98/5G-Monitoring-Framework.git
   cd 5G-Monitoring-Framework
   ```

2. Install required dependencies:

   Bash

   ```
   pip install -r core-ran-monitor/config/requirements.txt
   ```



## Usage

### Amarisoft Exporter

1. Configure your node IPs in `core-ran-monitor/config/config.ini`.

2. Run the exporter from the project root:

   Bash

   ```
   python3 -m core-ran-monitor.exporter.exporter_prometheus
   ```

### Kubernetes Network & Energy Tracking

Run the collectors on your worker nodes to generate local metrics:

```
python3 kubernetes-monitor/cluster-monitor/k8s_network_collector.py
python3 kubernetes-monitor/cluster-monitor/energy_consumption_collector.py
```

### VNF & Vehicle Telemetry

```
python3 kubernetes-monitor/vnf-monitor/vehicle_telemetry.py
python3 kubernetes-monitor/vnf-monitor/vobu_tracker.py
```



## Sample Metrics

| **Metric**               | **Type** | **Description**                                     |
| ------------------------ | -------- | --------------------------------------------------- |
| `amari_gnb_stats`        | Gauge    | Physical layer performance (PRB usage, throughput). |
| `pod_network_rx_bytes`   | Gauge    | Incoming traffic per Kubernetes Pod.                |
| `vobu_active_latitude`   | Gauge    | Geographic latitude of the serving vOBU instance.   |
| `cpu_total_energy_watts` | Gauge    | Estimated power consumption of the host node.       |



## License

This software is provided by the **University of Murcia** under a specific **Software License Agreement**.

For the full legal text, please refer to the LICENSE file included in this repository.