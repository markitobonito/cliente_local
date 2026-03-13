"""
QUIC Sender Module for Client

This module implements the QUICSender class responsible for sending files
to the bridge using QUIC protocol over UDP.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

from config import QUIC_PORT, MAX_FILE_SIZE


logger = logging.getLogger(__name__)


class QUICSender:
    """
    Handles sending files to the bridge via QUIC protocol.
    
    Attributes:
        bridge_ip: IP address of the bridge
        bridge_port: Port number for QUIC connection (default: 5000)
        max_retries: Maximum number of connection retry attempts (default: 3)
    """
    
    def __init__(self, bridge_ip: Optional[str] = None, bridge_port: int = QUIC_PORT):
        """
        Initialize the QUIC sender.
        
        Args:
            bridge_ip: IP address of the bridge (can be None initially)
            bridge_port: Port number for QUIC connection
        """
        self.bridge_ip = bridge_ip
        self.bridge_port = bridge_port
        self.max_retries = 3
        self._connection: Optional[QuicConnectionProtocol] = None
        
    def set_bridge_ip(self, bridge_ip: str) -> None:
        """
        Update the bridge IP address.
        
        Args:
            bridge_ip: New bridge IP address
        """
        self.bridge_ip = bridge_ip
        logger.info(f"Bridge IP updated to: {bridge_ip}")
        
    async def connect(self) -> bool:
        """
        Establish QUIC connection with the bridge using exponential backoff.
        
        Implements exponential backoff retry logic: 1s, 2s, 4s (max 3 retries)
        
        Returns:
            True if connection successful, False otherwise
            
        Requirements: 5.2
        """
        if not self.bridge_ip:
            logger.error("Cannot connect: bridge IP not available")
            return False
            
        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["file-transfer"],
        )
        configuration.verify_mode = False  # Disable certificate verification for LAN
        
        for attempt in range(self.max_retries):
            try:
                backoff_delay = 2 ** attempt  # 1s, 2s, 4s
                
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries} after {backoff_delay}s delay")
                    await asyncio.sleep(backoff_delay)
                
                logger.info(f"Attempting to connect to bridge at {self.bridge_ip}:{self.bridge_port}")
                
                async with connect(
                    self.bridge_ip,
                    self.bridge_port,
                    configuration=configuration,
                    create_protocol=QuicConnectionProtocol,
                ) as client:
                    self._connection = client
                    logger.info(f"Successfully connected to bridge at {self.bridge_ip}:{self.bridge_port}")
                    return True
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to connect after {self.max_retries} attempts")
                    return False
                    
        return False
        
    async def send_file(self, file_path: str) -> bool:
        """
        Read file and send it to the bridge via QUIC.
        
        Message format: filename\0file_data
        
        Args:
            file_path: Path to the file to send
            
        Returns:
            True if file sent successfully, False otherwise
            
        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
        """
        # Requirement 5.5: Check if bridge IP is available
        if not self.bridge_ip:
            logger.error("Cannot send file: bridge IP not available. Waiting for bridge announcement.")
            return False
            
        # Requirement 5.1: Read file contents
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return False
                
            if not file_path_obj.is_file():
                logger.error(f"Path is not a file: {file_path}")
                return False
                
            file_size = file_path_obj.stat().st_size
            
            if file_size > MAX_FILE_SIZE:
                logger.error(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE} bytes)")
                return False
                
            with open(file_path, 'rb') as f:
                file_data = f.read()
                
            filename = file_path_obj.name
            logger.info(f"Read file: {filename} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return False
            
        # Requirement 5.2: Establish QUIC connection
        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["file-transfer"],
        )
        configuration.verify_mode = False  # Disable certificate verification for LAN
        
        for attempt in range(self.max_retries):
            try:
                backoff_delay = 2 ** attempt  # 1s, 2s, 4s
                
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{self.max_retries} after {backoff_delay}s delay")
                    await asyncio.sleep(backoff_delay)
                
                logger.info(f"Connecting to bridge at {self.bridge_ip}:{self.bridge_port}")
                
                async with connect(
                    self.bridge_ip,
                    self.bridge_port,
                    configuration=configuration,
                    create_protocol=QuicConnectionProtocol,
                ) as client:
                    # Requirement 5.3: Send file name, size, and contents
                    # Format: filename\0file_data
                    message = filename.encode('utf-8') + b'\0' + file_data
                    
                    # Create a stream and send the data
                    stream_id = client._quic.get_next_available_stream_id()
                    client._quic.send_stream_data(stream_id, message, end_stream=True)
                    client.transmit()
                    
                    # Wait a bit to ensure data is transmitted
                    await asyncio.sleep(0.5)
                    
                    # Requirement 5.4: Log successful transfer
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"[{timestamp}] Successfully sent file: {filename} ({file_size} bytes) to {self.bridge_ip}")
                    
                    return True
                    
            except Exception as e:
                logger.error(f"Send attempt {attempt + 1} failed: {e}")
                
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to send file after {self.max_retries} attempts")
                    return False
                    
        return False
        
    def send_file_sync(self, file_path: str) -> bool:
        """
        Synchronous wrapper for send_file.
        
        Args:
            file_path: Path to the file to send
            
        Returns:
            True if file sent successfully, False otherwise
        """
        return asyncio.run(self.send_file(file_path))
