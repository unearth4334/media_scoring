FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create media directory
RUN mkdir -p /media

# Expose the default port
EXPOSE 7862

# Set default environment variables
ENV PUID=0
ENV PGID=0

# Start the application
CMD ["python", "app.py", "--dir", "/media", "--host", "0.0.0.0", "--port", "7862"]