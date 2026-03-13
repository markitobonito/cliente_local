"""
Bridge Core Module for LAN File Transfer System

This module implements the BridgeCore class which coordinates all bridge modules:
- MulticastListener: Receives HELLO/ALIVE messages from clients
- MulticastAnnouncer: Sends BRIDGE announcements periodically
- BridgeQUICReceiver: Receives files from clients via QUIC
- QUICForwarder: Forwards files to active clients
- ActiveClientTable: Maintains table of active clients with timeout

The bridge acts as the central coordinator for file distribution in the LAN.

Requirements: 1.5, 2.2, 3.1, 3.2, 4.1, 4.2, 6.1, 7.1, 9.1, 9.6, 9.8
"""

import asyncio
import logging
import signal
import sys
import threading
import time
from typing import Optional

from .multicast_listener import MulticastListener
from .multicast_announcer import MulticastAnnouncer
from .client_table import ActiveClientTable
from .quic_receiver import BridgeQUICReceiver
from .quic_forwarder import QUICForwarder
from .config import (
    BRIDGE_ANNOUNCEMENT_INTERVAL,
    CLEANUP_INTERVAL,
    CLIENT_TIMEOUT,
    ACTIVE_CLIENT_LOG_INTERVAL,
    MULTICAST_GROUP,
    MULTICAST_PORT,
    QUIC_PORT
)
from .utils import detect_local_ip, setup_logging


class BridgeCore:
    """
    Core coordinator for the bridge component.
    
    This class initializes and manages all bridge modules:
    - Multicast listener for client discovery
    - Multicast announcer for bridge IP advertisement
    - QUIC receiver for file reception
    - QUIC forwarder for file distribution
    - Active client table for client management
    
    The bridge runs multiple threads:
    - Multicast listener thread
    - Multicast announcer thread
    - Cleanup thread (every 2 seconds)
    - QUIC receiver thread
    - Active client logging thread (every 10 seconds)
    """
    
    def __init__(self):
        """Initialize the bridge core and all modules."""
        self.logger = setup_logging(__name__)
        
        # Initialize modules
        self.client_table = ActiveClientTable()
        self.listener = MulticastListener(MULTICAST_GROUP, MULTICAST_PORT)
        self.announcer = MulticastAnnouncer(MULTICAST_GROUP, MULTICAST_PORT)
        self.receiver = BridgeQUICReceiver(QUIC_PORT)
        self.forwarder = QUICForwarder(self.client_table)
        
        # State
        self._running = False
        self._local_ip: Optional[str] = None
        self._cleanup_thread: Optional[threading.Thread] = None
        self._logging_thread: Optional[threading.Thread] = None
        self._quic_thread: Optional[threading.Thread] = None
        
        self.logger.info("BridgeCore initialized")
    
    def start(self) -> None:
        """
        Start all bridge modules and threads.
        
        This method:
        1. Detects local IP address
        2. Starts multicast listener thread
        3. Starts multicast announcer thread (every 3 seconds)
        4. Starts cleanup thread (every 2 seconds)
        5. Starts QUIC receiver thread
        6. Starts active client logging thread (every 10 seconds)
        7. Sets up signal handlers for graceful shutdown
        
        Requirements: 1.5, 2.2, 3.1, 3.2, 4.1, 4.2, 6.1, 9.1, 9.8
        """
        try:
            # Detect local IP
            self._local_ip = detect_local_ip()
            
            # Requirement 9.1: Log bridge startup with local IP
            self.logger.info(f"=" * 60)
            self.logger.info(f"Bridge starting on {self._local_ip}")
            self.logger.info(f"Multicast: {MULTICAST_GROUP}:{MULTICAST_PORT}")
            self.logger.info(f"QUIC Port: {QUIC_PORT}")
            self.logger.info(f"=" * 60)
            
            self._running = True
            
            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Requirement 4.1, 4.2: Start multicast announcer thread (every 3 seconds)
            self.announcer.start_announcing(self._local_ip, BRIDGE_ANNOUNCEMENT_INTERVAL)
            self.logger.info(f"Multicast announcer started (interval: {BRIDGE_ANNOUNCEMENT_INTERVAL}s)")
            
            # Requirement 1.5, 2.2: Start multicast listener thread
            self.listener.start_listening(self.handle_client_message)
            self.logger.info("Multicast listener started")
            
            # Requirement 3.1, 3.2: Start cleanup thread (every 2 seconds)
            self._cleanup_thread = threading.Thread(target=self.cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            self.logger.info(f"Cleanup thread started (interval: {CLEANUP_INTERVAL}s, timeout: {CLIENT_TIMEOUT}s)")
            
            # Requirement 9.8: Start active client logging thread (every 10 seconds)
            self._logging_thread = threading.Thread(target=self.active_client_logging_loop, daemon=True)
            self._logging_thread.start()
            self.logger.info(f"Active client logging started (interval: {ACTIVE_CLIENT_LOG_INTERVAL}s)")
            
            # Requirement 6.1: Start QUIC receiver thread
            self.receiver.set_callback(self.handle_file_received)
            self._quic_thread = threading.Thread(target=self.receiver.start_listening_sync, daemon=True)
            self._quic_thread.start()
            self.logger.info(f"QUIC receiver started on port {QUIC_PORT}")
            
            self.logger.info("Bridge is now running. Press Ctrl+C to stop.")
            
            # Keep main thread alive
            while self._running:
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            self.stop()
            sys.exit(1)
    
    def handle_client_message(self, msg_type: str, client_ip: str) -> None:
        """
        Handle HELLO and ALIVE messages from clients.
        
        This callback is invoked by the MulticastListener when a client
        message is received. It updates the ActiveClientTable accordingly.
        
        Args:
            msg_type: Type of message ('HELLO' or 'ALIVE')
            client_ip: IP address of the client
            
        Requirements: 1.5, 2.2
        """
        if msg_type == 'HELLO':
            # Requirement 1.5: Add client to Active_Client_Table when HELLO is received
            self.client_table.add_client(client_ip)
        elif msg_type == 'ALIVE':
            # Requirement 2.2: Update timestamp when ALIVE is received
            self.client_table.update_client(client_ip)
        else:
            self.logger.warning(f"Unknown message type: {msg_type} from {client_ip}")
    
    def handle_file_received(self, sender_ip: str, filename: str, data: bytes) -> None:
        """
        Handle file received from a client.
        
        This callback is invoked by the BridgeQUICReceiver when a complete
        file is received. It coordinates the forwarding of the file to all
        active clients except the sender.
        
        Args:
            sender_ip: IP address of the client who sent the file
            filename: Name of the file
            data: File contents as bytes
            
        Requirements: 6.1, 7.1
        """
        self.logger.info(f"Processing received file '{filename}' from {sender_ip}")
        
        # Requirement 7.1: Forward file to all active clients except sender
        result = self.forwarder.forward_file(filename, data, sender_ip)
        
        # Log forwarding results
        self.logger.info(
            f"File '{filename}' forwarding complete: "
            f"{result['successful']} successful, {result['failed']} failed"
        )
        
        if result['errors']:
            for error in result['errors']:
                self.logger.error(f"Forwarding error: {error}")
    
    def cleanup_loop(self) -> None:
        """
        Periodically remove inactive clients from the table.
        
        This method runs in a separate thread and calls cleanup_inactive()
        every 2 seconds to remove clients that haven't sent a heartbeat
        in the last 10 seconds.
        
        Requirements: 3.1, 3.2
        """
        self.logger.info("Cleanup loop started")
        
        while self._running:
            try:
                # Requirement 3.1: Check table every 2 seconds
                time.sleep(CLEANUP_INTERVAL)
                
                # Requirement 3.2: Remove clients with timestamp > 10 seconds
                removed = self.client_table.cleanup_inactive(CLIENT_TIMEOUT)
                
                if removed:
                    self.logger.info(f"Cleanup removed {len(removed)} inactive client(s)")
                    
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
        
        self.logger.info("Cleanup loop stopped")
    
    def active_client_logging_loop(self) -> None:
        """
        Periodically log the count of active clients.
        
        This method runs in a separate thread and logs the number of
        active clients every 10 seconds.
        
        Requirements: 9.8
        """
        self.logger.info("Active client logging loop started")
        
        while self._running:
            try:
                # Requirement 9.8: Log active client count every 10 seconds
                time.sleep(ACTIVE_CLIENT_LOG_INTERVAL)
                
                count = self.client_table.get_client_count()
                clients = self.client_table.get_active_clients()
                
                if count > 0:
                    self.logger.info(f"Active clients: {count} - {clients}")
                else:
                    self.logger.info("Active clients: 0")
                    
            except Exception as e:
                self.logger.error(f"Error in active client logging loop: {e}")
        
        self.logger.info("Active client logging loop stopped")
    
    def _signal_handler(self, signum, frame) -> None:
        """
        Handle SIGINT and SIGTERM for graceful shutdown.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        self.logger.info(f"Received {signal_name}, shutting down gracefully...")
        self.stop()
    
    def stop(self) -> None:
        """
        Stop all bridge modules and threads gracefully.
        
        This method stops all running threads and modules in the correct order.
        """
        if not self._running:
            return
        
        self.logger.info("Stopping bridge...")
        self._running = False
        
        # Stop multicast modules
        self.listener.stop()
        self.announcer.stop()
        
        # Stop QUIC receiver
        self.receiver.stop()
        
        # Wait for threads to finish
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2.0)
        
        if self._logging_thread and self._logging_thread.is_alive():
            self._logging_thread.join(timeout=2.0)
        
        if self._quic_thread and self._quic_thread.is_alive():
            self._quic_thread.join(timeout=2.0)
        
        self.logger.info("Bridge stopped")


def main():
    """
    Main entry point for the bridge application.
    """
    bridge = BridgeCore()
    bridge.start()


if __name__ == "__main__":
    main()
