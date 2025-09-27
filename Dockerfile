FROM python:3.11-slim-bookworm

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      curl \
      ca-certificates \
      openssh-server \
      postgresql-client \
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
RUN chmod +x scripts/docker-entrypoint.sh

# Create media and logs directories
RUN mkdir -p /media /app/.logs

# Configure SSH server
RUN mkdir -p /var/run/sshd /root/.ssh \
 && chmod 700 /root/.ssh \
 && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
 && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Copy authorized keys for root SSH access
COPY authorized_keys /root/.ssh/authorized_keys
RUN chmod 600 /root/.ssh/authorized_keys

# Expose the default ports
EXPOSE 7862 22

# Set default environment variables
ENV PUID=0
ENV PGID=0

# Use the entrypoint script that properly handles configuration
CMD ["scripts/docker-entrypoint.sh"]