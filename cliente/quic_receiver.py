"""
QUIC Receiver Module for Client

This module implements the QUICReceiver class responsible for receiving files
from the bridge using QUIC protocol over UDP.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

from config import QUIC_PORT, RECEIVE_DIR


logger = logging.getLogger(__name__)


class FileReceiverProtocol(QuicConnectionProtocol):
    """
    Protocol handler for receiving files via QUIC.
    """
    
    def __init__(self, *args, save_directory: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_directory = save_directory
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
            
            # Save the file
            if self._save_file(filename, file_data):
                # Requirement 8.5: Log reception with filename and size
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[{timestamp}] Successfully received file: {filename} ({len(file_data)} bytes)")
            
        except Exception as e:
            logger.error(f"Error processing stream {stream_id}: {e}")
        finally:
            # Clean up stream data
            if stream_id in self._stream_data:
                del self._stream_data[stream_id]
                
    def _save_file(self, filename: str, data: bytes) -> bool:
        """
        Save received file to disk.
        
        Args:
            filename: Name of the file
            data: File contents
            
        Returns:
            True if file saved successfully, False otherwise
            
        Requirements: 8.4
        """
        try:
            # Create save directory if it doesn't exist
            save_dir = Path(self.save_directory)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename to prevent directory traversal
            safe_filename = Path(filename).name
            file_path = save_dir / safe_filename
            
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(data)
                
            logger.info(f"Saved file to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            return False


class QUICReceiver:
    """
    Handles receiving files from the bridge via QUIC protocol.
    
    Attributes:
        listen_port: Port number to listen on (default: 5000)
        save_directory: Directory to save received files
    """
    
    def __init__(self, listen_port: int = QUIC_PORT, save_directory: str = RECEIVE_DIR):
        """
        Initialize the QUIC receiver.
        
        Args:
            listen_port: Port number to listen on
            save_directory: Directory to save received files
        """
        self.listen_port = listen_port
        self.save_directory = save_directory
        self._server = None
        self._running = False
        
        # Create save directory if it doesn't exist
        Path(save_directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"QUIC receiver initialized: port={listen_port}, save_dir={save_directory}")
        
    async def start_listening(self) -> None:
        """
        Start QUIC server to accept incoming file transfers.
        
        This method runs indefinitely, listening for incoming QUIC connections
        and processing file transfers.
        
        Requirements: 8.1, 8.2
        """
        # Configure QUIC server
        configuration = QuicConfiguration(
            is_client=False,
            alpn_protocols=["file-transfer"],
        )
        
        # Generate self-signed certificate for QUIC (required by protocol)
        # In production, use proper certificates
        try:
            import ssl
            import tempfile
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
        
        logger.info(f"Starting QUIC server on 0.0.0.0:{self.listen_port}")
        
        try:
            self._running = True
            
            # Create protocol factory
            def create_protocol(*args, **kwargs):
                return FileReceiverProtocol(*args, save_directory=self.save_directory, **kwargs)
            
            # Start QUIC server
            await serve(
                "0.0.0.0",
                self.listen_port,
                configuration=configuration,
                create_protocol=create_protocol,
            )
            
            logger.info(f"QUIC server listening on port {self.listen_port}")
            
            # Keep server running
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"QUIC server error: {e}")
            raise
        finally:
            self._running = False
            
    def stop(self) -> None:
        """
        Stop the QUIC server.
        """
        logger.info("Stopping QUIC receiver")
        self._running = False
        
    def handle_incoming_file(self, stream) -> None:
        """
        Handle incoming file from a QUIC stream.
        
        This method is called by the protocol handler when a complete
        file has been received.
        
        Format expected: filename\0file_data
        
        Args:
            stream: QUIC stream containing file data
            
        Requirements: 8.3
        """
        # This method is implemented in FileReceiverProtocol.quic_event_received
        # and is kept here for interface compatibility
        pass
        
    def save_file(self, filename: str, data: bytes) -> bool:
        """
        Save received file to disk.
        
        Args:
            filename: Name of the file
            data: File contents
            
        Returns:
            True if file saved successfully, False otherwise
            
        Requirements: 8.4
        """
        try:
            # Create save directory if it doesn't exist
            save_dir = Path(self.save_directory)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize filename to prevent directory traversal
            safe_filename = Path(filename).name
            file_path = save_dir / safe_filename
            
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(data)
                
            # Requirement 8.5: Log reception with filename and size
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{timestamp}] Saved file: {filename} ({len(data)} bytes) to {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            return False
            
    def start_listening_sync(self) -> None:
        """
        Synchronous wrapper for start_listening.
        """
        asyncio.run(self.start_listening())
