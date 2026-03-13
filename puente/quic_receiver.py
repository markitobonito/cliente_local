"""
QUIC Receiver Module for Bridge

This module implements the BridgeQUICReceiver class responsible for receiving files
from clients using QUIC protocol over UDP. Unlike the client receiver, this stores
files in memory and tracks sender IP addresses for forwarding exclusion.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Callable, Optional

from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

from .config import QUIC_PORT


logger = logging.getLogger(__name__)


class BridgeFileReceiverProtocol(QuicConnectionProtocol):
    """
    Protocol handler for receiving files from clients via QUIC.
    
    This protocol tracks the sender's IP address and maintains files in memory
    for forwarding to other clients.
    """
    
    def __init__(self, *args, callback: Optional[Callable] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = callback
        self._stream_data = {}
        
    def quic_event_received(self, event: QuicEvent) -> None:
        """
        Handle QUIC events, specifically stream data reception.
        
        Args:
            event: QUIC event to process
        """
        if isinstance(event, StreamDataReceived):
            stream_id = event.stream_id
            
            # Accumulate data for this stream
            if stream_id not in self._stream_data:
                self._stream_data[stream_id] = b''
            self._stream_data[stream_id] += event.data
            
            # If stream is finished, process the complete file
            if event.end_stream:
                self._handle_complete_stream(stream_id)
                
    def _handle_complete_stream(self, stream_id: int) -> None:
        """
        Process a complete stream containing file data.
        
        Args:
            stream_id: ID of the completed stream
        """
        data = self._stream_data.get(stream_id, b'')
        
        if not data:
            logger.warning(f"Received empty data on stream {stream_id}")
            return
            
        try:
            # Parse filename\0file_data format
            null_index = data.find(b'\0')
            
            if null_index == -1:
                logger.error("Invalid file format: no null byte delimiter found")
                return
                
            filename = data[:null_index].decode('utf-8')
            file_data = data[null_index + 1:]
            
            # Requirement 6.3: Store sender's IP address
            # Get sender IP from the connection
            sender_ip = self._quic._network_paths[0].addr[0] if self._quic._network_paths else "unknown"
            
            # Requirement 6.4: Log reception with sender IP and filename
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{timestamp}] Received file from {sender_ip}: {filename} ({len(file_data)} bytes)")
            
            # Requirement 6.5: Maintain file in memory and notify bridge core via callback
            if self.callback:
                self.callback(sender_ip, filename, file_data)
            
        except Exception as e:
            logger.error(f"Error processing stream {stream_id}: {e}")
        finally:
            # Clean up stream data
            if stream_id in self._stream_data:
                del self._stream_data[stream_id]


class BridgeQUICReceiver:
    """
    Handles receiving files from clients via QUIC protocol.
    
    The bridge receiver differs from the client receiver in that it:
    - Stores files in memory (not to disk)
    - Tracks sender IP addresses
    - Uses callback pattern to notify bridge core for forwarding
    
    Attributes:
        listen_port: Port number to listen on (default: 5000)
        callback: Function to call when file is received (sender_ip, filename, data)
    """
    
    def __init__(self, listen_port: int = QUIC_PORT):
        """
        Initialize the bridge QUIC receiver.
        
        Args:
            listen_port: Port number to listen on
        """
        self.listen_port = listen_port
        self._callback = None
        self._server = None
        self._running = False
        
        logger.info(f"Bridge QUIC receiver initialized: port={listen_port}")
        
    def set_callback(self, callback: Callable[[str, str, bytes], None]) -> None:
        """
        Set the callback function to be called when a file is received.
        
        Args:
            callback: Function with signature (sender_ip: str, filename: str, data: bytes) -> None
        """
        self._callback = callback
        
    async def start_listening(self) -> None:
        """
        Start QUIC server to accept incoming file transfers from clients.
        
        This method runs indefinitely, listening for incoming QUIC connections
        and processing file transfers. When a file is received, it calls the
        registered callback with the sender IP, filename, and file data.
        
        Requirements: 6.1, 6.2
        """
        # Configure QUIC server
        configuration = QuicConfiguration(
            is_client=False,
            alpn_protocols=["file-transfer"],
        )
        
        # Generate self-signed certificate for QUIC (required by protocol)
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Generate certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).sign(private_key, hashes.SHA256())
            
            # Write certificate and key to temporary files
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as cert_file:
                cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
                cert_path = cert_file.name
                
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as key_file:
                key_file.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                key_path = key_file.name
                
            configuration.load_cert_chain(cert_path, key_path)
            
            # Clean up temporary files
            os.unlink(cert_path)
            os.unlink(key_path)
            
        except Exception as e:
            logger.error(f"Failed to generate certificate: {e}")
            raise
        
        logger.info(f"Starting bridge QUIC server on 0.0.0.0:{self.listen_port}")
        
        try:
            self._running = True
            
            # Create protocol factory with callback
            def create_protocol(*args, **kwargs):
                return BridgeFileReceiverProtocol(*args, callback=self._callback, **kwargs)
            
            # Start QUIC server
            await serve(
                "0.0.0.0",
                self.listen_port,
                configuration=configuration,
                create_protocol=create_protocol,
            )
            
            logger.info(f"Bridge QUIC server listening on port {self.listen_port}")
            
            # Keep server running
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Bridge QUIC server error: {e}")
            raise
        finally:
            self._running = False
            
    def stop(self) -> None:
        """
        Stop the QUIC server.
        """
        logger.info("Stopping bridge QUIC receiver")
        self._running = False
        
    def handle_incoming_file(self, stream, sender_ip: str) -> tuple[str, bytes]:
        """
        Handle incoming file from a QUIC stream.
        
        This method is implemented in BridgeFileReceiverProtocol.quic_event_received
        and is kept here for interface compatibility with the design document.
        
        Format expected: filename\0file_data
        
        Args:
            stream: QUIC stream containing file data
            sender_ip: IP address of the sender
            
        Returns:
            Tuple of (filename, file_data)
            
        Requirements: 6.2, 6.3
        """
        # This method is implemented in BridgeFileReceiverProtocol
        # and is kept here for interface compatibility
        pass
        
    def start_listening_sync(self) -> None:
        """
        Synchronous wrapper for start_listening.
        """
        asyncio.run(self.start_listening())
