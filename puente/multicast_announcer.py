"""
Multicast Announcer Module for LAN File Transfer System Bridge.

This module handles sending periodic BRIDGE announcements to clients
via multicast, allowing clients to discover the bridge's IP address.
"""

import socket
import struct
import threading
import time
import logging
from typing import Optional

from .config import MULTICAST_GROUP, MULTICAST_PORT, MULTICAST_TTL, BRIDGE_ANNOUNCEMENT_INTERVAL
from .utils import detect_local_ip, setup_logging


class MulticastAnnouncer:
    """
    Handles sending periodic BRIDGE announcements via multicast.
    
    This module is responsible for:
    - Detecting the bridge's local IP address
    - Sending BRIDGE|<ip> messages every 3 seconds via multicast
    - Managing multicast socket configuration for cross-platform compatibility
    - Ensuring clients can discover the bridge's IP address
    """
    
    def __init__(self, multicast_group: str = MULTICAST_GROUP,
                 multicast_port: int = MULTICAST_PORT):
        """
        Initialize the Multicast Announcer.
        
        Args:
            multicast_group: Multicast group address (default: 239.255.255.250)
            multicast_port: Multicast port (default: 4000)
        """
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.logger = setup_logging(__name__)
        
        # State
        self._running = False
        self._announcer_thread: Optional[threading.Thread] = None
        self._send_socket: Optional[socket.socket] = None
        self._local_ip: Optional[str] = None
    
    def _create_send_socket(self) -> socket.socket:
        """
        Create and configure a socket for sending multicast messages.
        
        Configures TTL, IP_MULTICAST_IF, and SO_REUSEADDR for cross-platform
        compatibility (especially macOS).
        
        Returns:
            socket.socket: Configured multicast send socket
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Enable address reuse
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Set TTL to 1 (local network only)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
        
        # Set IP_MULTICAST_IF for macOS compatibility
        # This ensures the multicast packets are sent on the correct interface
        if self._local_ip:
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(self._local_ip)
            )
        
        self.logger.info(f"Multicast send socket configured: {self.multicast_group}:{self.multicast_port}")
        
        return sock
    
    def detect_local_ip(self) -> str:
        """
        Detect the bridge's local IP address.
        
        Uses the shared utility function to detect the local IP address
        across different operating systems (macOS, Linux, Windows).
        
        Returns:
            str: The local IP address (e.g., "192.168.1.50")
            
        Raises:
            RuntimeError: If unable to detect local IP
        """
        return detect_local_ip()
    
    def send_bridge_announcement(self, local_ip: str) -> None:
        """
        Send a single BRIDGE announcement message.
        
        Sends a BRIDGE|<ip> message to the multicast group.
        
        Args:
            local_ip: The bridge's local IP address to announce
        """
        if self._send_socket is None:
            raise RuntimeError("Send socket not initialized")
        
        message = f"BRIDGE|{local_ip}"
        try:
            self._send_socket.sendto(
                message.encode('utf-8'),
                (self.multicast_group, self.multicast_port)
            )
            self.logger.debug(f"Sent BRIDGE announcement: {local_ip}")
        except Exception as e:
            self.logger.error(f"Failed to send BRIDGE announcement: {e}")
    
    def start_announcing(self, local_ip: str, interval: int = BRIDGE_ANNOUNCEMENT_INTERVAL) -> None:
        """
        Start sending periodic BRIDGE announcements.
        
        This method runs in a separate thread and continuously sends
        BRIDGE|<ip> messages at the specified interval (default: 3 seconds).
        
        Args:
            local_ip: The bridge's local IP address to announce
            interval: Time in seconds between announcements (default: 3)
        """
        self._running = True
        self._local_ip = local_ip
        
        def announcer_loop():
            try:
                # Create send socket
                self._send_socket = self._create_send_socket()
                
                self.logger.info(f"Started announcing bridge IP: {local_ip} every {interval}s")
                
                while self._running:
                    # Send BRIDGE announcement
                    self.send_bridge_announcement(local_ip)
                    
                    # Wait for the interval
                    time.sleep(interval)
            
            except Exception as e:
                self.logger.error(f"Failed to start multicast announcer: {e}")
            finally:
                self.logger.info("Stopped announcing bridge IP")
        
        # Start announcer thread
        self._announcer_thread = threading.Thread(target=announcer_loop, daemon=True)
        self._announcer_thread.start()
    
    def stop(self) -> None:
        """
        Stop the multicast announcer.
        
        Stops the announcer thread and closes the socket.
        """
        self.logger.info("Stopping multicast announcer...")
        self._running = False
        
        # Wait for thread to finish
        if self._announcer_thread and self._announcer_thread.is_alive():
            self._announcer_thread.join(timeout=2.0)
        
        # Close socket
        if self._send_socket:
            self._send_socket.close()
            self._send_socket = None
        
        self.logger.info("Multicast announcer stopped")
    
    def is_running(self) -> bool:
        """
        Check if the announcer is currently running.
        
        Returns:
            bool: True if announcing, False otherwise
        """
        return self._running
