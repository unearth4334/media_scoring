FROM python:3.11-slim-bookworm

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      curl \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*


# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Create media directory
RUN mkdir -p /media

# Expose the default port
EXPOSE 7862

# Set default environment variables
ENV PUID=0
ENV PGID=0

# Use the entrypoint script that properly handles configuration
CMD ["./docker-entrypoint.sh"]