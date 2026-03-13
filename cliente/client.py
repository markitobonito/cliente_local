#!/usr/bin/env python3
"""
Client Main Coordination Module

This module serves as the main entry point for the LAN File Transfer System client.
It initializes and coordinates all client modules including discovery, QUIC sender/receiver,
Flask web server, and monitoring threads.

Requirements: 1.1, 1.2, 2.1, 2.3, 5.1, 8.1, 9.1, 9.2
"""

import asyncio
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from discovery import DiscoveryModule
from quic_sender import QUICSender
from quic_receiver import QUICReceiver
from app import FlaskWebApp
from msg_monitor import MessageMonitor
from video_monitor import VideoMonitor
from config import (
    QUIC_PORT,
    FLASK_PORT,
    RECEIVE_DIR,
    HEARTBEAT_INTERVAL
)
from utils import setup_logging, detect_local_ip


# Global flag for graceful shutdown
shutdown_event = threading.Event()


class ClientCoordinator:
    """
    Main coordinator for the client application.
    
    Responsibilities:
    - Initialize all client modules
    - Start discovery and heartbeat threads
    - Start QUIC receiver thread
    - Start Flask web server thread
    - Start message and video monitor threads
    - Handle graceful shutdown on SIGINT/SIGTERM
    """
    
    def __init__(self):
        """Initialize the client coordinator."""
        self.logger = setup_logging(__name__)
        
        # State
        self.local_ip: Optional[str] = None
        self.bridge_ip: Optional[str] = None
        
        # Modules
        self.discovery: Optional[DiscoveryModule] = None
        self.quic_sender: Optional[QUICSender] = None
        self.quic_receiver: Optional[QUICReceiver] = None
        self.flask_app: Optional[FlaskWebApp] = None
        self.msg_monitor: Optional[MessageMonitor] = None
        self.video_monitor: Optional[VideoMonitor] = None
        
        # Threads
        self.quic_receiver_thread: Optional[threading.Thread] = None
        self.flask_thread: Optional[threading.Thread] = None
        
        self.logger.info("ClientCoordinator initialized")
    
    def _bridge_callback(self, bridge_ip: str) -> None:
        """
        Callback function called when bridge IP is received.
        
        Updates the bridge IP in the QUIC sender so it can send files.
        
        Args:
            bridge_ip: IP address of the bridge
        """
        if self.bridge_ip != bridge_ip:
            self.bridge_ip = bridge_ip
            self.logger.info(f"Bridge discovered at: {bridge_ip}")
            
            # Update QUIC sender with bridge IP
            if self.quic_sender:
                self.quic_sender.set_bridge_ip(bridge_ip)
    
    def initialize_modules(self) -> None:
        """
        Initialize all client modules.
        
        Requirements: 1.1, 5.1, 8.1
        """
        self.logger.info("Initializing client modules...")
        
        # Requirement 1.1: Detect local IP
        try:
            self.local_ip = detect_local_ip()
            self.logger.info(f"Detected local IP: {self.local_ip}")
        except Exception as e:
            self.logger.error(f"Failed to detect local IP: {e}")
            sys.exit(1)
        
        # Initialize discovery module
        self.discovery = DiscoveryModule()
        
        # Initialize QUIC sender (bridge IP will be set by discovery callback)
        self.quic_sender = QUICSender(bridge_ip=None, bridge_port=QUIC_PORT)
        
        # Initialize QUIC receiver
        self.quic_receiver = QUICReceiver(
            listen_port=QUIC_PORT,
            save_directory=RECEIVE_DIR
        )
        
        # Initialize Flask web app
        self.flask_app = FlaskWebApp(self.quic_sender)
        
        # Initialize message monitor
        self.msg_monitor = MessageMonitor(watch_directory=RECEIVE_DIR)
        
        # Initialize video monitor
        self.video_monitor = VideoMonitor(watch_directory=RECEIVE_DIR)
        
        self.logger.info("All modules initialized successfully")
    
    def start_discovery(self) -> None:
        """
        Start discovery module for listening to BRIDGE announcements
        and sending HELLO/ALIVE messages.
        
        Requirements: 1.2, 2.1, 2.3
        """
        self.logger.info("Starting discovery module...")
        
        # Start discovery with bridge callback
        self.discovery.start(bridge_callback=self._bridge_callback)
        
        self.logger.info(
            f"Discovery started: HELLO sent, heartbeat every {HEARTBEAT_INTERVAL}s"
        )
    
    def start_quic_receiver(self) -> None:
        """
        Start QUIC receiver thread to listen for incoming file transfers.
        
        Requirements: 8.1
        """
        self.logger.info(f"Starting QUIC receiver on port {QUIC_PORT}...")
        
        def quic_receiver_loop():
            """Run QUIC receiver in asyncio event loop."""
            try:
                asyncio.run(self.quic_receiver.start_listening())
            except Exception as e:
                self.logger.error(f"QUIC receiver error: {e}", exc_info=True)
        
        self.quic_receiver_thread = threading.Thread(
            target=quic_receiver_loop,
            daemon=True,
            name="QUICReceiver"
        )
        self.quic_receiver_thread.start()
        
        self.logger.info(f"QUIC receiver started on port {QUIC_PORT}")
    
    def start_flask_server(self) -> None:
        """
        Start Flask web server thread for web interface.
        
        Requirements: 5.1
        """
        self.logger.info(f"Starting Flask web server on port {FLASK_PORT}...")
        
        def flask_server_loop():
            """Run Flask server."""
            try:
                self.flask_app.run(host='0.0.0.0', port=FLASK_PORT, debug=False)
            except Exception as e:
                self.logger.error(f"Flask server error: {e}", exc_info=True)
        
        self.flask_thread = threading.Thread(
            target=flask_server_loop,
            daemon=True,
            name="FlaskServer"
        )
        self.flask_thread.start()
        
        self.logger.info(
            f"Flask web server started on http://0.0.0.0:{FLASK_PORT}"
        )
    
    def start_monitors(self) -> None:
        """
        Start message and video monitor threads.
        
        Requirements: 9.1, 9.2
        """
        self.logger.info("Starting monitor threads...")
        
        # Start message monitor
        self.msg_monitor.start_monitoring()
        self.logger.info("Message monitor started")
        
        # Start video monitor
        self.video_monitor.start_monitoring()
        self.logger.info("Video monitor started")
    
    def start(self) -> None:
        """
        Start all client components.
        
        This method:
        1. Initializes all modules
        2. Starts discovery thread (HELLO + heartbeat)
        3. Starts QUIC receiver thread
        4. Starts Flask web server thread
        5. Starts message and video monitor threads
        
        Requirements: 1.1, 1.2, 2.1, 2.3, 5.1, 8.1, 9.1, 9.2
        """
        # Requirement 9.1: Log client startup with local IP
        self.logger.info("=" * 60)
        self.logger.info("LAN File Transfer System - Client Starting")
        self.logger.info("=" * 60)
        
        # Initialize all modules
        self.initialize_modules()
        
        # Requirement 9.1: Log client startup with local IP
        self.logger.info(f"Client starting with local IP: {self.local_ip}")
        
        # Start discovery (sends HELLO and starts heartbeat)
        # Requirements: 1.2, 2.1, 2.3
        self.start_discovery()
        
        # Start QUIC receiver
        # Requirement: 8.1
        self.start_quic_receiver()
        
        # Start Flask web server
        # Requirement: 5.1
        self.start_flask_server()
        
        # Start monitors
        # Requirements: 9.1, 9.2
        self.start_monitors()
        
        self.logger.info("=" * 60)
        self.logger.info("Client started successfully!")
        self.logger.info(f"Local IP: {self.local_ip}")
        self.logger.info(f"Web Interface: http://localhost:{FLASK_PORT}")
        self.logger.info(f"QUIC Port: {QUIC_PORT}")
        self.logger.info(f"Receive Directory: {RECEIVE_DIR}")
        self.logger.info("Waiting for bridge announcement...")
        self.logger.info("=" * 60)
    
    def stop(self) -> None:
        """
        Stop all client components gracefully.
        
        Handles SIGINT and SIGTERM for graceful shutdown.
        """
        self.logger.info("=" * 60)
        self.logger.info("Shutting down client...")
        self.logger.info("=" * 60)
        
        # Stop discovery module
        if self.discovery:
            self.logger.info("Stopping discovery module...")
            self.discovery.stop()
        
        # Stop QUIC receiver
        if self.quic_receiver:
            self.logger.info("Stopping QUIC receiver...")
            self.quic_receiver.stop()
        
        # Stop monitors
        if self.msg_monitor:
            self.logger.info("Stopping message monitor...")
            self.msg_monitor.stop_monitoring()
        
        if self.video_monitor:
            self.logger.info("Stopping video monitor...")
            self.video_monitor.stop_monitoring()
        
        # Note: Flask server will stop when main thread exits (daemon thread)
        
        self.logger.info("Client shutdown complete")
        self.logger.info("=" * 60)


def signal_handler(signum, frame):
    """
    Handle SIGINT (Ctrl+C) and SIGTERM signals for graceful shutdown.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


def main():
    """
    Main entry point for the client application.
    
    Sets up signal handlers, starts the client coordinator,
    and waits for shutdown signal.
    """
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger(__name__)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start client coordinator
    coordinator = ClientCoordinator()
    
    try:
        coordinator.start()
        
        # Wait for shutdown signal
        while not shutdown_event.is_set():
            time.sleep(1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        # Graceful shutdown
        coordinator.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
