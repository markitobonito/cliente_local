# Use python:3.11-slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bridge source files
COPY . .

# Expose port 5000/udp (QUIC)
EXPOSE 5000/udp

# Set CMD to run bridge.py directly
CMD ["python", "bridge.py"]
