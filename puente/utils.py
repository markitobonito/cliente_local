"""
Shared utilities for the bridge component.
Provides IP detection and logging configuration.
"""

import socket
import logging
import sys
from typing import Optional


def detect_local_ip() -> str:
    """
    Detect the local IP address for the current operating system.
    
    This function works across macOS, Linux, and Windows by creating
    a UDP socket and connecting to an external address (without actually
    sending data) to determine which local interface would be used.
    
    Returns:
        str: The local IP address (e.g., "192.168.1.50")
        
    Raises:
        RuntimeError: If unable to detect local IP
    """
    try:
        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to an external address (doesn't actually send data)
        # Using Google's DNS server as a reference point
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        return local_ip
    except Exception as e:
        raise RuntimeError(f"Failed to detect local IP: {e}")


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger
