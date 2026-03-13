# Cliente - LAN File Transfer System

Cliente component for the LAN file transfer system. This application runs on each node in the local network and provides file sharing, alert notifications with TTS, and scheduled video playback capabilities.

## Features

- **Automatic Network Discovery**: Announces presence via multicast and discovers the bridge automatically
- **Web Interface**: User-friendly interface for file uploads, alerts, and video scheduling
- **File Sharing**: Send and receive files through the bridge to all other clients
- **Alert System**: Send text alerts with TTS (Text-to-Speech) and visual notifications
- **Video Playback**: Upload videos with immediate, silent, or scheduled playback options
- **Docker Deployment**: Fully containerized with Docker Compose for easy setup

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Network that supports multicast (239.255.255.250)
- At least one bridge instance running on the network

### Starting the Client

1. Navigate to the client directory:
```bash
cd localcito/cliente
```

2. Start the client with Docker Compose:
```bash
docker-compose up -d
```

3. Access the web interface:
```
http://localhost:1492
```

### Stopping the Client

```bash
docker-compose down
```

### Viewing Logs

```bash
docker-compose logs -f cliente
```

## Web Interface

The client provides a web interface accessible at `http://localhost:1492` with three main features:

### 1. File Upload

Upload any file to share with all other clients on the network.

- Maximum file size: 100MB
- Files are automatically distributed to all active clients (except the sender)
- Received files are saved to `./received_files/` directory

**Usage:**
1. Click "Choose File" and select a file
2. Click "Upload File"
3. Wait for confirmation message

### 2. Send Alert

Send text alerts that will be announced via TTS on all client machines.

- Repetitions: 1-10 times
- Message: Any text message
- Alerts trigger both audio (TTS) and visual notifications

**Usage:**
1. Enter the number of repetitions (1-10)
2. Type your alert message
3. Click "Send Alert"

**Example:**
- Repetitions: 3
- Message: "Meeting in 5 minutes"
- Result: All clients will hear the message 3 times

### 3. Upload Video

Upload videos with playback control options.

**Playback Options:**

- **Play Now**: Immediate playback with audio
- **Play Silent**: Immediate playback without audio
- **Schedule**: Play at specific time on specific days

**Scheduled Playback Format:**
- Time: HH:MM (24-hour format, e.g., 14:30)
- Days: 1=Monday, 2=Tuesday, ..., 7=Sunday
- Multiple days: Comma-separated (e.g., 1,3,5 for Mon, Wed, Fri)

**Usage:**
1. Select a video file (.mp4, .avi, .mkv, .mov)
2. Choose playback option
3. For scheduled videos, set time and days
4. Click "Upload Video"

**Examples:**
- Play now: Video plays immediately with audio
- Silent: Video plays immediately without audio
- Schedule 14:30 on days 1,3,5: Video plays Mon/Wed/Fri at 2:30 PM

## System Architecture

### Components

The client consists of several modules running concurrently:

1. **Discovery Module** (`discovery.py`)
   - Announces client presence via multicast (HELLO message)
   - Sends heartbeat every 5 seconds (ALIVE message)
   - Listens for bridge announcements (BRIDGE message)

2. **QUIC Sender** (`quic_sender.py`)
   - Sends files to the bridge via QUIC/UDP
   - Handles connection establishment and retries

3. **QUIC Receiver** (`quic_receiver.py`)
   - Listens for incoming files from the bridge
   - Saves received files to `./received_files/`

4. **Flask Web App** (`app.py`)
   - Provides web interface on port 1492
   - Handles file uploads, alerts, and video uploads
   - Integrates with QUIC sender for transmission

5. **Message Monitor** (`msg_monitor.py`)
   - Monitors `./received_files/` for `.msg` files
   - Parses alert format: `repetitions|message`
   - Executes TTS and shows notifications
   - Deletes processed alerts

6. **Video Monitor** (`video_monitor.py`)
   - Monitors `./received_files/` for video files
   - Parses filename flags (SILENT, SCHED)
   - Plays videos immediately or schedules playback
   - Deletes videos after playback (immediate/silent only)

### Network Ports

- **1492/TCP**: Flask web interface
- **5000/UDP**: QUIC file reception
- **4000/UDP**: Multicast discovery (239.255.255.250)

### File Formats

**Alert Messages (.msg):**
```
<repetitions>|<message>
```
Example: `3|Meeting in 5 minutes`

**Video Flags:**
- No flag: `video.mp4` (play immediately with audio)
- Silent: `video.SILENT.mp4` (play immediately without audio)
- Scheduled: `video.SCHED_14:30_1,3,5.mp4` (play Mon/Wed/Fri at 14:30)

## Configuration

Configuration is managed in `config.py`:

```python
# Multicast settings
MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 4000

# QUIC settings
QUIC_PORT = 5000

# Flask settings
FLASK_PORT = 1492

# File limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Alert settings
MAX_ALERT_REPETITIONS = 10

# Video settings
VIDEO_EXTENSIONS = [".mp4", ".avi", ".mkv", ".mov"]
MONITOR_INTERVAL = 2  # seconds
```

## Docker Configuration

### Dockerfile

The client Docker image includes:
- Python 3.11 slim base
- System dependencies: espeak (TTS), ffmpeg, vlc (video player)
- Python dependencies from `requirements.txt`
- Exposed ports: 1492/TCP, 5000/UDP

### docker-compose.yml

```yaml
services:
  cliente:
    build: .
    network_mode: host  # Required for multicast
    restart: unless-stopped
    volumes:
      - ./received_files:/app/received_files
      - ./templates:/app/templates
      - ./static:/app/static
```

**Important:** `network_mode: host` is required for multicast discovery to work properly.

## Troubleshooting

### Client Not Discovering Bridge

**Symptoms:**
- Logs show "Bridge not discovered" errors
- Cannot send files

**Solutions:**
1. Verify bridge is running: Check bridge logs
2. Check multicast support: Ensure network allows multicast traffic
3. Check firewall: Allow UDP port 4000 for multicast
4. Verify network: Client and bridge must be on same LAN

**Test multicast connectivity:**
```bash
# On bridge machine, check logs for HELLO messages
docker-compose logs -f puente | grep HELLO

# On client machine, check logs for BRIDGE messages
docker-compose logs -f cliente | grep BRIDGE
```

### Cannot Access Web Interface

**Symptoms:**
- Cannot open http://localhost:1492
- Connection refused error

**Solutions:**
1. Check if container is running:
```bash
docker-compose ps
```

2. Check if port is in use:
```bash
netstat -an | grep 1492
```

3. Check container logs:
```bash
docker-compose logs cliente
```

4. Try accessing from container IP:
```bash
docker inspect cliente_cliente_1 | grep IPAddress
```

### File Upload Fails

**Symptoms:**
- Upload returns error
- Files not received by other clients

**Solutions:**
1. Check file size: Must be under 100MB
2. Check bridge connection: Verify bridge IP is discovered
3. Check QUIC connectivity: Ensure UDP port 5000 is accessible
4. Check disk space: Ensure sufficient space in `./received_files/`

**Verify QUIC connectivity:**
```bash
# Check if bridge is listening on port 5000
# On bridge machine:
netstat -an | grep 5000
```

### TTS Not Working

**Symptoms:**
- Alerts received but no audio
- Visual notification appears but no speech

**Solutions:**
1. Check audio system: Ensure audio is not muted
2. Check espeak installation:
```bash
docker exec -it cliente_cliente_1 espeak "test"
```

3. Check logs for TTS errors:
```bash
docker-compose logs cliente | grep -i tts
```

4. Verify .msg file format: Must be `repetitions|message`

### Video Not Playing

**Symptoms:**
- Video received but doesn't play
- Scheduled video doesn't play at specified time

**Solutions:**
1. Check video format: Must be .mp4, .avi, .mkv, or .mov
2. Check VLC installation:
```bash
docker exec -it cliente_cliente_1 vlc --version
```

3. Check video monitor logs:
```bash
docker-compose logs cliente | grep -i video
```

4. For scheduled videos, verify time format: Must be HH:MM (24-hour)
5. For scheduled videos, verify days: Must be 1-7 (1=Monday, 7=Sunday)

### High CPU Usage

**Symptoms:**
- Container using excessive CPU
- System slowdown

**Solutions:**
1. Check monitor intervals: Default is 2 seconds
2. Check for stuck video playback:
```bash
docker exec -it cliente_cliente_1 ps aux | grep vlc
```

3. Restart container:
```bash
docker-compose restart
```

### Received Files Not Appearing

**Symptoms:**
- Other clients send files but not received
- `./received_files/` directory empty

**Solutions:**
1. Check QUIC receiver: Verify listening on port 5000
```bash
docker-compose logs cliente | grep "QUIC receiver"
```

2. Check file permissions:
```bash
ls -la received_files/
```

3. Check volume mount:
```bash
docker inspect cliente_cliente_1 | grep -A 5 Mounts
```

4. Check firewall: Allow UDP port 5000 inbound

## Development

### Running Without Docker

1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install espeak ffmpeg vlc

# macOS
brew install espeak ffmpeg vlc
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the client:
```bash
python client.py
```

### Testing

Run unit tests:
```bash
pytest tests/
```

Run property-based tests:
```bash
pytest tests/ -k property
```

### Logs

Logs are written to stdout and captured by Docker:
- Client startup and IP detection
- Discovery messages (HELLO, ALIVE, BRIDGE)
- File send/receive operations
- Alert processing
- Video playback
- Errors and warnings

**Log levels:**
- INFO: Normal operations
- WARNING: Non-critical issues
- ERROR: Critical failures

## Security Considerations

- **Network Trust**: This system assumes a trusted LAN environment
- **No Authentication**: No authentication between clients and bridge
- **No Encryption**: Files are transferred without encryption (QUIC provides transport security)
- **File Validation**: Limited file validation - do not use on untrusted networks
- **Resource Limits**: 100MB file size limit to prevent resource exhaustion

## Performance

- **File Transfer**: QUIC provides efficient UDP-based transfer
- **Concurrent Operations**: All modules run in separate threads
- **Memory Usage**: Files are held in memory during transfer
- **Network Overhead**: Minimal - heartbeat every 5 seconds, bridge announcement every 3 seconds

## License

See project root for license information.

## Support

For issues and questions:
1. Check logs: `docker-compose logs -f cliente`
2. Review troubleshooting section above
3. Verify network configuration (multicast, firewall)
4. Check bridge is running and accessible
