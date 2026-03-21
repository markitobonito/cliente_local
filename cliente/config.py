"""
Configuration constants for the client component.
"""

# Multicast configuration
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 4000
MULTICAST_TTL = 1

# QUIC configuration
QUIC_PORT = 5000

# Flask configuration
FLASK_PORT = 1492

# Bridge API configuration
BRIDGE_API_PORT = 8080

# Heartbeat configuration
HEARTBEAT_INTERVAL = 5  # seconds

# File reception configuration
RECEIVE_DIR = "./received_files"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Alert configuration
MAX_ALERT_REPETITIONS = 10
TTS_ENGINE = "pyttsx3"

# Video configuration
VIDEO_EXTENSIONS = [".mp4", ".avi", ".mkv", ".mov"]
VIDEO_PLAYER = "vlc"
MONITOR_INTERVAL = 2  # seconds
