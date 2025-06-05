# Scheduler for Spiral v2.7.0 - Cron Jobs and Task Scheduling
FROM python:3.11-alpine

# Build arguments
ARG VERSION=v2.7.0

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Labels for better container management
LABEL maintainer="Spiral AI Team" \
      version="$VERSION" \
      description="Cron Job Scheduler for Nightly Tasks" \
      gpu.required="false"

# Install system dependencies
RUN apk add --no-cache \
    bash \
    curl \
    jq \
    tzdata \
    && rm -rf /var/cache/apk/*

# Create app user for security
RUN addgroup -g 1001 spiral && \
    adduser -D -s /bin/bash -u 1001 -G spiral spiral

# Create necessary directories
RUN mkdir -p /app/logs \
             /app/tasks \
             /app/config \
    && chown -R spiral:spiral /app

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Copy application code
COPY scheduler.py /app/

# Create simple health check
COPY <<EOF /app/health_check.sh
#!/bin/bash
set -e
if ! pgrep -f "scheduler.py" > /dev/null; then
    echo "ERROR: scheduler.py not running"
    exit 1
fi
echo "Health check: OK"
exit 0
EOF

RUN chmod +x /app/health_check.sh

# Switch to non-root user
USER spiral

# Health check configuration
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD /app/health_check.sh

# Expose metrics port (if needed)
EXPOSE 8003

# Volumes for data persistence
VOLUME ["/app/logs", "/app/tasks"]

# Default command
CMD ["python3", "/app/scheduler.py"] 