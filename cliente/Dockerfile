# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    espeak \
    ffmpeg \
    vlc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all client source files
COPY . .

# Create required directories
RUN mkdir -p received_files templates static

# Expose Flask port (TCP) and QUIC port (UDP)
EXPOSE 1492/tcp
EXPOSE 5000/udp

# Run the client
CMD ["python", "client.py"]
