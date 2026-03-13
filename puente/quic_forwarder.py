"""
QUIC Forwarder Module for Bridge

This module implements the QUICForwarder class responsible for forwarding files
to all active clients except the sender using QUIC protocol over UDP.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import asyncio
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

from client_table import ActiveClientTable
from config import QUIC_PORT, MAX_FORWARDER_WORKERS


logger = logging.getLogger(__name__)


class QUICForwarder:
    """
    Handles forwarding files to active clients via QUIC protocol.
    
    The forwarder retrieves the list of active clients from the ActiveClientTable,
    excludes the sender's IP, and forwards the file to all remaining clients in
    parallel using a ThreadPoolExecutor.
    
    Individual client failures do not stop the forwarding process.
    
    Attributes:
        client_table: Reference to the ActiveClientTable
        max_workers: Maximum number of parallel forwarding workers
    """
    
    def __init__(self, client_table: ActiveClientTable):
        """
        Initialize the QUIC forwarder.
        
        Args:
            client_table: ActiveClientTable instance for retrieving active clients
        """
        self.client_table = client_table
        self.max_workers = MAX_FORWARDER_WORKERS
        
        logger.info(f"QUIC forwarder initialized: max_workers={self.max_workers}")
        
    def forward_file(self, filename: str, data: bytes, sender_ip: str) -> Dict[str, int]:
        """
        Forward file to all active clients except the sender.
        
        This method:
        1. Retrieves all active clients from the ActiveClientTable (Req 7.1)
        2. Excludes the sender's IP from the recipient list (Req 7.2)
        3. Establishes QUIC connections with each client (Req 7.3)
        4. Sends the file to each client (Req 7.4)
        5. Logs successful and failed forwards (Req 7.5)
        6. Continues forwarding even if individual transfers fail (Req 7.6)
        
        Args:
            filename: Name of the file to forward
            data: File contents as bytes
            sender_ip: IP address of the client who sent the file
            
        Returns:
            Dictionary with keys:
                - 'successful': Number of successful forwards
                - 'failed': Number of failed forwards
                - 'errors': List of error messages for failed forwards
                
        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
        """
        # Requirement 7.1: Retrieve all IPs from Active_Client_Table
        active_clients = self.client_table.get_active_clients()
        
        logger.info(f"Forwarding file '{filename}' ({len(data)} bytes) from {sender_ip}")
        logger.debug(f"Active clients before exclusion: {active_clients}")
        
        # Requirement 7.2: Exclude sender's IP from the list
        recipients = [ip for ip in active_clients if ip != sender_ip]
        
        if not recipients:
            logger.info(f"No recipients to forward to (sender: {sender_ip}, active clients: {len(active_clients)})")
            return {'successful': 0, 'failed': 0, 'errors': []}
        
        logger.info(f"Forwarding to {len(recipients)} recipient(s): {recipients}")
        
        # Forward to clients in parallel using ThreadPoolExecutor
        successful = 0
        failed = 0
        errors = []
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(recipients))) as executor:
            # Submit all forwarding tasks
            future_to_ip = {
                executor.submit(self.send_to_client, ip, filename, data): ip
                for ip in recipients
            }
            
            # Requirement 7.6: Handle individual client failures without stopping
            for future in as_completed(future_to_ip):
                client_ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        successful += 1
                        logger.info(f"Successfully forwarded to {client_ip}")
                    else:
                        failed += 1
                        error_msg = f"Failed to forward to {client_ip}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                except Exception as e:
                    failed += 1
                    error_msg = f"Exception forwarding to {client_ip}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        # Requirement 7.5: Log number of successful and failed forwards
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(
            f"[{timestamp}] File forwarding complete for '{filename}': "
            f"{successful} successful, {failed} failed"
        )
        
        return {
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    def send_to_client(self, client_ip: str, filename: str, data: bytes) -> bool:
        """
        Send file to a specific client via QUIC.
        
        This method:
        1. Establishes a QUIC connection with the client (Req 7.3)
        2. Sends the file name, size, and contents (Req 7.4)
        3. Handles connection failures gracefully (Req 7.6)
        
        Args:
            client_ip: IP address of the client
            filename: Name of the file
            data: File contents as bytes
            
        Returns:
            True if successful, False otherwise
            
        Requirements: 7.3, 7.4, 7.6
        """
        try:
            # Run async send in a new event loop
            return asyncio.run(self._send_to_client_async(client_ip, filename, data))
        except Exception as e:
            logger.error(f"Error sending to {client_ip}: {e}")
            return False
    
    async def _send_to_client_async(self, client_ip: str, filename: str, data: bytes) -> bool:
        """
        Async implementation of send_to_client.
        
        Args:
            client_ip: IP address of the client
            filename: Name of the file
            data: File contents as bytes
            
        Returns:
            True if successful, False otherwise
        """
        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["file-transfer"],
        )
        
        # Disable certificate verification for local network
        configuration.verify_mode = False
        
        try:
            # Requirement 7.3: Establish QUIC connection with client
            logger.debug(f"Connecting to client {client_ip}:{QUIC_PORT}")
            
            async with connect(
                client_ip,
                QUIC_PORT,
                configuration=configuration,
                create_protocol=QuicConnectionProtocol,
            ) as protocol:
                # Requirement 7.4: Send file name, size, and contents
                # Format: filename\0file_data
                message = f"{filename}\0".encode('utf-8') + data
                
                # Create a stream and send data
                stream_id = protocol._quic.get_next_available_stream_id()
                protocol._quic.send_stream_data(stream_id, message, end_stream=True)
                
                # Transmit the data
                protocol.transmit()
                
                # Wait a bit for transmission to complete
                await asyncio.sleep(0.1)
                
                logger.debug(f"Sent {len(message)} bytes to {client_ip}")
                return True
                
        except ConnectionRefusedError:
            logger.error(f"Connection refused by {client_ip}:{QUIC_PORT}")
            return False
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout to {client_ip}:{QUIC_PORT}")
            return False
        except Exception as e:
            logger.error(f"Failed to send to {client_ip}: {e}")
            return False
