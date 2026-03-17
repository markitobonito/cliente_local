"""
Configuration constants for the bridge component.
"""

# Multicast configuration
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 4000
MULTICAST_TTL = 1

# QUIC configuration
QUIC_PORT = 5000

# HTTP API configuration
BRIDGE_API_PORT = 8080

# Bridge announcement configuration
BRIDGE_ANNOUNCEMENT_INTERVAL = 3  # seconds

# Client management configuration
CLEANUP_INTERVAL = 2  # seconds
CLIENT_TIMEOUT = 10  # seconds

# File transfer configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FORWARDER_WORKERS = 10

# Logging configuration
ACTIVE_CLIENT_LOG_INTERVAL = 10  # seconds
