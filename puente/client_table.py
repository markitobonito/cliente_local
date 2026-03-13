"""
Active Client Table for Bridge

This module implements the ActiveClientTable class which maintains a thread-safe
table of active clients with timestamp tracking for timeout management.

Requirements:
- 1.5: Add clients when HELLO message is received
- 2.2: Update client timestamps when ALIVE message is received
- 3.1: Check table periodically (every 2 seconds)
- 3.2: Remove clients with timestamps older than 10 seconds
- 3.3: Log client removal with IP address
"""

import threading
import time
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ActiveClientTable:
    """
    Thread-safe table for tracking active clients with timestamp-based timeout.
    
    Data structure: dict[str, float] mapping IP address to timestamp
    Client timeout: 10 seconds (configurable)
    Thread-safe operations using threading.Lock
    """
    
    def __init__(self):
        """Initialize the Active Client Table with empty client dictionary and lock."""
        self._clients: Dict[str, float] = {}
        self._lock = threading.Lock()
        logger.info("ActiveClientTable initialized")
    
    def add_client(self, ip: str) -> None:
        """
        Add or update a client with current timestamp.
        
        If the client already exists, this updates their timestamp.
        This method is called when a HELLO message is received.
        
        Args:
            ip: IP address of the client to add
            
        Requirements: 1.5
        """
        with self._lock:
            current_time = time.time()
            is_new = ip not in self._clients
            self._clients[ip] = current_time
            
            if is_new:
                logger.info(f"Client added to Active_Client_Table: {ip}")
            else:
                logger.debug(f"Client timestamp updated: {ip}")
    
    def update_client(self, ip: str) -> None:
        """
        Update the timestamp for an existing client.
        
        This method is called when an ALIVE message is received.
        If the client doesn't exist, it will be added.
        
        Args:
            ip: IP address of the client to update
            
        Requirements: 2.2
        """
        with self._lock:
            current_time = time.time()
            if ip in self._clients:
                self._clients[ip] = current_time
                logger.debug(f"Client heartbeat received: {ip}")
            else:
                # Client not in table, add it
                self._clients[ip] = current_time
                logger.info(f"Client added via ALIVE message: {ip}")
    
    def remove_client(self, ip: str) -> None:
        """
        Remove a client from the table.
        
        Args:
            ip: IP address of the client to remove
            
        Requirements: 3.3
        """
        with self._lock:
            if ip in self._clients:
                del self._clients[ip]
                logger.info(f"Client removed from Active_Client_Table: {ip}")
            else:
                logger.warning(f"Attempted to remove non-existent client: {ip}")
    
    def get_active_clients(self) -> List[str]:
        """
        Return a list of all active client IP addresses.
        
        Returns:
            List of IP addresses currently in the table
            
        Requirements: 7.1
        """
        with self._lock:
            return list(self._clients.keys())
    
    def cleanup_inactive(self, timeout: int = 10) -> List[str]:
        """
        Remove clients with timestamps older than the specified timeout.
        
        This method should be called periodically (every 2 seconds) to maintain
        the table and remove inactive clients.
        
        Args:
            timeout: Maximum age in seconds before a client is considered inactive
                    (default: 10 seconds)
        
        Returns:
            List of IP addresses that were removed
            
        Requirements: 3.1, 3.2, 3.3
        """
        with self._lock:
            current_time = time.time()
            removed_clients = []
            
            # Find clients that have timed out
            for ip, timestamp in list(self._clients.items()):
                age = current_time - timestamp
                if age > timeout:
                    removed_clients.append(ip)
                    del self._clients[ip]
                    logger.info(f"Client removed due to inactivity (age: {age:.1f}s): {ip}")
            
            if removed_clients:
                logger.info(f"Cleanup removed {len(removed_clients)} inactive client(s)")
            
            return removed_clients
    
    def get_client_count(self) -> int:
        """
        Return the number of active clients in the table.
        
        Returns:
            Number of clients currently in the table
            
        Requirements: 9.8
        """
        with self._lock:
            return len(self._clients)
    
    def get_client_info(self, ip: str) -> float | None:
        """
        Get the timestamp for a specific client.
        
        Args:
            ip: IP address of the client
            
        Returns:
            Timestamp of the client, or None if not found
        """
        with self._lock:
            return self._clients.get(ip)
