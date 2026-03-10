"""
Identity Manager Module

This module handles the matching between IMSIs and temporary network IDs (RAN/AMF UE IDs).
It processes UE data across different network nodes to maintain a consistent 
identity mapping.

Module: identity_manager.py
"""

import threading
import queue
import asyncio
import logging
import time
from configparser import ConfigParser

# Internal project modules
import config.logs as logs
import collectors.metrics_collector as collector

# Initialize logger and config
logger = logging.getLogger(logs.__name__)
parser = ConfigParser()
parser.read('config.ini')

# Global UE identity list
ueList = []

def save_imsis():
    """Persists the current IMSI list to a local file."""
    try:
        with open('imsis.txt', 'w') as f:
            for item in ueList:
                # Assuming item has an imsi attribute (from models.py)
                f.write(f"{item.imsi if hasattr(item, 'imsi') else item}\n")
        logger.info("IMSI list saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save IMSIs: {e}")

class IdentityMatcher:
    """
    Handles the logic for matching IMSIs with UE IDs across different 
    network scenarios (Local cell, Handover, Other Operators).
    """
    def __init__(self, lock):
        self.lock = lock

    def process_ue_data(self, server_data, core_data, ran_data):
        """Analyze and correlate UE data from Server, Core, and RAN nodes."""
        ue_list_core = core_data.get('ue_list', [])
        
        imsi_list = [ue.get('imsi') for ue in ue_list_core]
        tac_list = [ue.get('tac') for ue in ue_list_core]

        print(f"Connected UEs in Core: {imsi_list}")
        print(f"Associated TACs: {tac_list}")

        if len(imsi_list) != len(tac_list):
            logger.error("Data Mismatch: IMSI and TAC lists have different lengths.")
            return

        # Matrix for IMSI-TAC association
        imsi_tac_map = list(zip(imsi_list, tac_list))
        print("IMSI-TAC Mapping Matrix:")
        for entry in imsi_tac_map:
            print(f"  -> IMSI: {entry[0]} | TAC: {entry[1]}")

        # Scenario Dispatcher based on TAC
        for ue_core in ue_list_core:
            tac = ue_core.get('tac')
            if tac == 1:
                logger.debug("Scenario 1 detected: Local Callbox Cell")
                # self.__handle_local_scenario(server_data.get('ue_list', []), ue_list_core)
            elif tac == 101:
                logger.debug("Scenario 2 detected: External Cell (ATICA/LV)")
                self.__handle_external_cell_scenario(ue_list_core, ran_data.get('ue_list', []))
            else:
                logger.debug("Scenario detected: External Operator / Roaming")
                self.__handle_external_operator(ue_list_core)

    def __handle_local_scenario(self, ue_list_server, ue_list_core):
        """Case 1: UEs connected to the Callbox cell are also registered in Core."""
        results = []
        for ue_srv in ue_list_server:
            for ue_core in ue_list_core:
                if (ue_srv.get('ran_ue_id') == ue_core.get('ran_ue_id') and 
                    ue_srv.get('amf_ue_id') == ue_core.get('amf_ue_id')):
                    
                    imsi = ue_core.get('imsi')
                    results.append([ue_core.get('ran_ue_id'), ue_core.get('amf_ue_id'), imsi])
                    print(f"Matched Local UE: RAN_ID={ue_core.get('ran_ue_id')} -> IMSI={imsi}")
        
        print(f"Local Match Matrix: {results}")

    def __handle_external_cell_scenario(self, ue_list_core, ue_list_ran):
        """Case 2: UE belongs to the same core but is connected to a different cell."""
        results = []
        for ue_core in ue_list_core:
            for ue_ran in ue_list_ran:
                ran_id = ue_core.get('ran_ue_id')
                amf_id = ue_core.get('amf_ue_id')
                
                cells = ue_ran.get('cells', [])
                cell_id = cells[0].get('cell_id') if cells else "Unknown"

                if ue_ran.get('ran_ue_id') == ran_id and ue_ran.get('amf_ue_id') == amf_id:
                    imsi = ue_core.get('imsi')
                    print(f"Matched External UE: IMSI={imsi} on Cell={cell_id}")
                    results.append([ran_id, amf_id, imsi])
        
        print(f"External Cell Match Matrix: {results}")

    def __handle_external_operator(self, ue_list_core):
        """Scenario for UEs belonging to other PLMNs."""
        local_plmn = "99910"
        connected_to_plmn = []
        other_operators = []

        for ue in ue_list_core:
            imsi = ue.get('imsi')
            if ue.get('tac_plmn') == local_plmn:
                connected_to_plmn.append(imsi)
            else:
                other_operators.append(imsi)

        print(f"UEs in Local PLMN ({local_plmn}): {connected_to_plmn}")
        print(f"UEs in Other PLMNs: {other_operators}")

    def run(self):
        """Main loop to start data collection threads and process identity matching."""
        # Load existing IMSIs from file
        try:
            with open('imsis.txt', 'r') as f:
                for line in f:
                    ueList.append(line.strip())
            logger.info(f"Identity Manager started. Existing IMSIs loaded: {len(ueList)}")
        except FileNotFoundError:
            logger.warning("No imsis.txt found. Starting with an empty identity list.")

        request_limit = int(parser["Amari"].get("request_limit", 20))

        while True:
            try:
                # Queues for node communication
                q_server, q_core, q_ran = queue.Queue(), queue.Queue(), queue.Queue()

                # Worker threads
                threads = [
                    threading.Thread(target=asyncio.run, args=(collector.callbox_connection(q_server),), daemon=True),
                    threading.Thread(target=asyncio.run, args=(collector.core_connection(q_core),), daemon=True),
                    threading.Thread(target=asyncio.run, args=(collector.ran_connection(q_ran),), daemon=True)
                ]

                for t in threads:
                    t.start()

                for _ in range(request_limit):
                    s = q_server.get(block=True)
                    c = q_core.get(block=True)
                    r = q_ran.get(block=True)

                    # Index 1 contains the UE list from the collector's response
                    self.process_ue_data(s[1], c[1], r[1])

                for t in threads:
                    t.join()

            except Exception as e:
                logger.error(f"Identity Manager Loop Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    # Start the identity matching thread
    matcher = IdentityMatcher(threading.Lock())
    matcher.run()