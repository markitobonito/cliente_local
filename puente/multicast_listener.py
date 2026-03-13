"""
Multicast Listener Module for LAN File Transfer System Bridge.

This module handles receiving multicast messages from clients,
specifically HELLO and ALIVE messages for client discovery and heartbeat.
"""

import socket
import struct
import threading
import logging
from typing import Optional, Callable, Tuple

from .config import MULTICAST_GROUP, MULTICAST_PORT
from .utils import setup_logging


class MulticastListener:
    """
    Handles receiving multicast messages from clients.
    
    This module is responsible for:
    - Listening for HELLO messages (client discovery)
    - Listening for ALIVE messages (client heartbeat)
    - Parsing multicast messages to extract message type and client IP
    - Notifying the bridge core via callback when messages are received
    - Managing multicast socket configuration for cross-platform compatibility
    """
    
    def __init__(self, multicast_group: str = MULTICAST_GROUP,
                 multicast_port: int = MULTICAST_PORT):
        """
        Initialize the Multicast Listener.
        
        Args:
            multicast_group: Multicast group address (default: 239.255.255.250)
            multicast_port: Multicast port (default: 4000)
        """
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.logger = setup_logging(__name__)
        
        # State
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._recv_socket: Optional[socket.socket] = None
    
    def _create_recv_socket(self) -> socket.socket:
        """
        Create and configure a socket for receiving multicast messages.
        
        Configures SO_REUSEADDR and joins the multicast group.
        
        Returns:
            socket.socket: Configured multicast receive socket
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Enable address reuse
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to the multicast port
        sock.bind(('', self.multicast_port))
        
        # Join the multicast group
        mreq = struct.pack('4sl', socket.inet_aton(self.multicast_group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Set timeout for non-blocking behavior
        sock.settimeout(1.0)
        
        self.logger.info(f"Multicast socket configured: {self.multicast_group}:{self.multicast_port}")
        
        return sock
    
    def parse_message(self, data: bytes) -> Tuple[str, str]:
        """
        Parse a multicast message to extract message type and client IP.
        
        Expected format: TYPE|IP
        Where TYPE is 'HELLO' or 'ALIVE'
        
        Args:
            data: Raw message bytes received from multicast
            
        Returns:
            Tuple[str, str]: (message_type, client_ip)
            
        Raises:
            ValueError: If message format is invalid
        """
        try:
            message = data.decode('utf-8').strip()
            
            # Check for pipe delimiter
            if '|' not in message:
                raise ValueError(f"Invalid message format (no delimiter): {message}")
            
            # Split on first pipe only
            parts = message.split('|', 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid message format (wrong parts): {message}")
            
            msg_type, client_ip = parts
            
            # Validate message type
            if msg_type not in ('HELLO', 'ALIVE'):
                raise ValueError(f"Invalid message type: {msg_type}")
            
            # Basic IP validation (non-empty)
            if not client_ip:
                raise ValueError("Empty IP address in message")
            
            return msg_type, client_ip
            
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode message: {e}")
    
    def start_listening(self, callback: Callable[[str, str], None]) -> None:
        """
        Start listening for multicast messages from clients.
        
        This method runs in a separate thread and continuously listens for
        HELLO and ALIVE messages. When a valid message is received, it calls
        the provided callback function with the message type and client IP.
        
        Args:
            callback: Callback function to call when a message is received.
                     Signature: callback(message_type: str, client_ip: str)
                     where message_type is 'HELLO' or 'ALIVE'
        """
        self._running = True
        
        def listener_loop():
            try:
                if self._recv_socket is None:
                    self._recv_socket = self._create_recv_socket()
                
                self.logger.info("Started listening for client messages")
                
                while self._running:
                    try:
                        data, addr = self._recv_socket.recvfrom(1024)
                        
                        # Parse the message
                        try:
                            msg_type, client_ip = self.parse_message(data)
                            
                            # Log based on message type
                            if msg_type == 'HELLO':
                                self.logger.info(f"Received HELLO from {client_ip}")
                            else:  # ALIVE
                                self.logger.debug(f"Received ALIVE from {client_ip}")
                            
                            # Notify bridge core via callback
                            callback(msg_type, client_ip)
                            
                        except ValueError as e:
                            self.logger.warning(f"Invalid message from {addr}: {e}")
                    
                    except socket.timeout:
                        # Timeout is expected, continue listening
                        continue
                    except Exception as e:
                        if self._running:
                            self.logger.error(f"Error receiving multicast message: {e}")
            
            except Exception as e:
                self.logger.error(f"Failed to start multicast listener: {e}")
            finally:
                self.logger.info("Stopped listening for client messages")
        
        # Start listener thread
        self._listener_thread = threading.Thread(target=listener_loop, daemon=True)
        self._listener_thread.start()
    
    def stop(self) -> None:
        """
        Stop the multicast listener.
        
        Stops the listener thread and closes the socket.
        """
        self.logger.info("Stopping multicast listener...")
        self._running = False
        
        # Wait for thread to finish
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        
        # Close socket
        if self._recv_socket:
            self._recv_socket.close()
            self._recv_socket = None
        
        self.logger.info("Multicast listener stopped")
    
    def is_running(self) -> bool:
        """
        Check if the listener is currently running.
        
        Returns:
            bool: True if listening, False otherwise
        """
        return self._running
