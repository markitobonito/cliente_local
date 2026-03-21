"""
Discovery Module for LAN File Transfer System Client.

This module handles multicast-based discovery and heartbeat functionality,
allowing clients to announce their presence and discover the bridge.
"""

import socket
import struct
import threading
import time
import logging
import requests
from typing import Optional, Callable

from config import (
    MULTICAST_GROUP,
    MULTICAST_PORT,
    MULTICAST_TTL,
    HEARTBEAT_INTERVAL,
    BRIDGE_API_PORT
)
from utils import detect_local_ip, setup_logging


class DiscoveryModule:
    """
    Handles client discovery and heartbeat operations using multicast UDP.
    
    This module is responsible for:
    - Detecting the local IP address
    - Sending HELLO messages when the client starts
    - Sending periodic ALIVE messages (heartbeat)
    - Listening for BRIDGE announcements from the bridge
    - Managing multicast socket configuration for cross-platform compatibility
    """
    
    def __init__(self, multicast_group: str = MULTICAST_GROUP, 
                 multicast_port: int = MULTICAST_PORT):
        """
        Initialize the Discovery Module.
        
        Args:
            multicast_group: Multicast group address (default: 239.255.255.250)
            multicast_port: Multicast port (default: 4000)
        """
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.logger = setup_logging(__name__)
        
        # State
        self.local_ip: Optional[str] = None
        self.bridge_ip: Optional[str] = None
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._http_fallback_thread: Optional[threading.Thread] = None
        self._multicast_received = False
        
        # Sockets
        self._send_socket: Optional[socket.socket] = None
        self._recv_socket: Optional[socket.socket] = None
    
    def detect_local_ip(self) -> str:
        """
        Detect the local IP address of this client.
        
        Uses the utility function from utils.py which works across
        macOS, Linux, and Windows.
        
        Returns:
            str: The local IP address (e.g., "192.168.1.100")
            
        Raises:
            RuntimeError: If unable to detect local IP
        """
        if self.local_ip is None:
            self.local_ip = detect_local_ip()
            self.logger.info(f"Detected local IP: {self.local_ip}")
        return self.local_ip
    
    def _create_send_socket(self) -> socket.socket:
        """
        Create and configure a socket for sending multicast messages.
        
        Configures IP_MULTICAST_IF and SO_REUSEADDR for macOS compatibility.
        
        Returns:
            socket.socket: Configured multicast send socket
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Set TTL to 1 (local network only)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
        
        # Set IP_MULTICAST_IF for macOS compatibility
        # This ensures the multicast packets go out on the correct interface
        if self.local_ip:
            try:
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(self.local_ip)
                )
                self.logger.info(f"Multicast interface set to: {self.local_ip}")
            except OSError as e:
                self.logger.warning(f"Failed to set IP_MULTICAST_IF to {self.local_ip}: {e}")
                self.logger.warning("Multicast may not work correctly. Consider running with sudo or checking firewall settings.")
        
        # Enable address reuse
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        return sock
    
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
        
        return sock
    
    def send_hello(self, local_ip: str) -> None:
        """
        Send a HELLO message via multicast to announce client presence.
        
        Format: HELLO|<ip>
        
        Args:
            local_ip: The local IP address to announce
        """
        message = f"HELLO|{local_ip}"
        try:
            if self._send_socket is None:
                self._send_socket = self._create_send_socket()
            
            self._send_socket.sendto(
                message.encode('utf-8'),
                (self.multicast_group, self.multicast_port)
            )
            self.logger.info(f"Sent HELLO message: {message}")
        except OSError as e:
            self.logger.error(f"Failed to send HELLO message (OSError {e.errno}): {e}")
            self.logger.error(f"This may be a network configuration issue. Check firewall settings.")
        except Exception as e:
            self.logger.error(f"Failed to send HELLO message: {e}", exc_info=True)
    
    def send_alive(self, local_ip: str) -> None:
        """
        Send an ALIVE message via multicast to maintain presence.
        
        Format: ALIVE|<ip>
        
        Args:
            local_ip: The local IP address to announce
        """
        message = f"ALIVE|{local_ip}"
        try:
            if self._send_socket is None:
                self._send_socket = self._create_send_socket()
            
            self._send_socket.sendto(
                message.encode('utf-8'),
                (self.multicast_group, self.multicast_port)
            )
            self.logger.debug(f"Sent ALIVE message: {message}")
        except OSError as e:
            self.logger.error(f"Failed to send ALIVE message (OSError {e.errno}): {e}")
        except Exception as e:
            self.logger.error(f"Failed to send ALIVE message: {e}")
    
    def listen_for_bridge(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Listen for BRIDGE announcements from the bridge.
        
        This method runs in a separate thread and continuously listens for
        BRIDGE|<ip> messages. When received, it updates the stored bridge IP
        and optionally calls a callback function.
        
        Args:
            callback: Optional callback function to call when bridge IP is received.
                     The callback receives the bridge IP as a string argument.
        """
        self._running = True
        
        try:
            if self._recv_socket is None:
                self._recv_socket = self._create_recv_socket()
            
            self.logger.info("Started listening for BRIDGE announcements")
            
            while self._running:
                try:
                    data, addr = self._recv_socket.recvfrom(1024)
                    message = data.decode('utf-8').strip()
                    
                    # Parse message format: TYPE|IP
                    if '|' in message:
                        msg_type, ip = message.split('|', 1)
                        
                        if msg_type == 'BRIDGE':
                            self._multicast_received = True
                            old_bridge_ip = self.bridge_ip
                            self.bridge_ip = ip
                            
                            if old_bridge_ip != ip:
                                self.logger.info(f"Received BRIDGE announcement: {ip}")
                            
                            # Call callback if provided
                            if callback:
                                callback(ip)
                
                except socket.timeout:
                    # Timeout is expected, continue listening
                    continue
                except Exception as e:
                    if self._running:
                        self.logger.error(f"Error receiving multicast message: {e}")
        
        except Exception as e:
            self.logger.error(f"Failed to start multicast listener: {e}")
        finally:
            self.logger.info("Stopped listening for BRIDGE announcements")
    
    def _try_http_discovery(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """
        HTTP fallback for bridge discovery when multicast fails.
        
        This method waits 10 seconds for multicast to work. If no BRIDGE
        announcement is received, it tries HTTP requests to common gateway IPs
        to find the bridge.
        
        Args:
            callback: Optional callback function to call when bridge IP is found.
        """
        # Wait 10 seconds for multicast to work
        for _ in range(10):
            if not self._running:
                return
            if self._multicast_received:
                self.logger.info("Multicast working, HTTP fallback not needed")
                return
            time.sleep(1)
        
        if not self._running:
            return
        
        self.logger.warning("No multicast BRIDGE announcement received after 10 seconds")
        self.logger.info("Trying HTTP fallback discovery...")
        
        # Generate candidate IPs based on local IP
        candidates = []
        if self.local_ip:
            # Try gateway IPs in same subnet
            parts = self.local_ip.split('.')
            if len(parts) == 4:
                subnet = '.'.join(parts[:3])
                # Try .1 (common gateway), .100, .101, .254
                candidates.extend([
                    f"{subnet}.1",
                    f"{subnet}.100",
                    f"{subnet}.101",
                    f"{subnet}.254"
                ])
        
        # Also try common private network gateways
        candidates.extend([
            "192.168.0.1",
            "192.168.1.1",
            "192.168.0.100",
            "192.168.1.100",
            "10.0.0.1",
            "10.0.1.1"
        ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for ip in candidates:
            if ip not in seen:
                seen.add(ip)
                unique_candidates.append(ip)
        
        self.logger.info(f"Trying HTTP discovery on {len(unique_candidates)} candidate IPs...")
        
        # Try each candidate
        for candidate_ip in unique_candidates:
            if not self._running:
                return
            
            if self._multicast_received:
                # Multicast started working, stop HTTP fallback
                return
            
            try:
                url = f"http://{candidate_ip}:{BRIDGE_API_PORT}/api/bridge-info"
                response = requests.get(url, timeout=1)
                
                if response.status_code == 200:
                    data = response.json()
                    bridge_ip = data.get('bridge_ip')
                    
                    if bridge_ip:
                        self.logger.info(f"✓ Bridge found via HTTP at {bridge_ip}")
                        self.bridge_ip = bridge_ip
                        
                        # Call callback
                        if callback:
                            callback(bridge_ip)
                        
                        return
            
            except requests.exceptions.Timeout:
                # Timeout is expected for non-bridge IPs
                pass
            except requests.exceptions.ConnectionError:
                # Connection refused is expected for non-bridge IPs
                pass
            except Exception as e:
                # Log unexpected errors but continue trying
                self.logger.debug(f"HTTP discovery error for {candidate_ip}: {e}")
        
        self.logger.error("❌ HTTP fallback discovery failed - no bridge found")
        self.logger.error("Possible solutions:")
        self.logger.error("  1. Ensure bridge is running and accessible")
        self.logger.error("  2. Check firewall settings on both client and bridge")
        self.logger.error("  3. Verify both devices are on the same network")
        self.logger.error("  4. Check router IGMP snooping settings")
    
    def start_heartbeat(self, local_ip: str, interval: int = HEARTBEAT_INTERVAL) -> None:
        """
        Start sending periodic ALIVE messages (heartbeat).
        
        This method runs in a separate thread and sends ALIVE messages
        at the specified interval until stop() is called.
        
        Args:
            local_ip: The local IP address to announce
            interval: Interval between heartbeat messages in seconds (default: 5)
        """
        self._running = True
        
        def heartbeat_loop():
            self.logger.info(f"Started heartbeat with interval {interval}s")
            while self._running:
                self.send_alive(local_ip)
                time.sleep(interval)
            self.logger.info("Stopped heartbeat")
        
        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def start(self, bridge_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Start the discovery module.
        
        This method:
        1. Detects the local IP
        2. Sends a HELLO message
        3. Starts the heartbeat thread
        4. Starts the bridge listener thread
        5. Starts the HTTP fallback thread (tries after 10s if multicast fails)
        
        Args:
            bridge_callback: Optional callback for when bridge IP is received
        """
        try:
            # Detect local IP
            local_ip = self.detect_local_ip()
            self.logger.info(f"Discovery module starting with IP: {local_ip}")
            
            # Send initial HELLO message
            self.send_hello(local_ip)
            
            # Start heartbeat
            self.start_heartbeat(local_ip)
            
            # Start listening for bridge announcements
            self._listener_thread = threading.Thread(
                target=self.listen_for_bridge,
                args=(bridge_callback,),
                daemon=True
            )
            self._listener_thread.start()
            
            # Start HTTP fallback thread
            self._http_fallback_thread = threading.Thread(
                target=self._try_http_discovery,
                args=(bridge_callback,),
                daemon=True
            )
            self._http_fallback_thread.start()
            
            self.logger.info("Discovery module started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start discovery module: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        """
        Stop the discovery module.
        
        Stops all threads and closes sockets.
        """
        self.logger.info("Stopping discovery module...")
        self._running = False
        
        # Wait for threads to finish
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        
        if self._http_fallback_thread and self._http_fallback_thread.is_alive():
            self._http_fallback_thread.join(timeout=2.0)
        
        # Close sockets
        if self._send_socket:
            self._send_socket.close()
            self._send_socket = None
        
        if self._recv_socket:
            self._recv_socket.close()
            self._recv_socket = None
        
        self.logger.info("Discovery module stopped")
    
    def get_bridge_ip(self) -> Optional[str]:
        """
        Get the currently stored bridge IP address.
        
        Returns:
            Optional[str]: The bridge IP address, or None if not yet discovered
        """
        return self.bridge_ip
 