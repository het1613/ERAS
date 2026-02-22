FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    ffmpeg \
    git \
    pkg-config \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libavdevice-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy shared utilities (will be copied from project root context)
COPY shared/ /app/shared/

# Copy and install dependencies
COPY services/audio-processing/requirements.txt /app/requirements.txt
# Upgrade pip and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy service code
# Create directory structure to match imports (since main.py might expect to be in a package or imports might need adjustment)
# The original file copied to /app/main.py but imports were `from shared.kafka_client ...`
# If we run `python main.py` at /app, it works if shared is at /app/shared.

COPY services/audio-processing/main.py /app/main.py

# Run the service
CMD ["python", "main.py"]

