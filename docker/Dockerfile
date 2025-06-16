# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files following new structure
COPY config/ ./config/
COPY core/ ./core/
COPY database/ ./database/
COPY web/ ./web/
COPY utils/ ./utils/
COPY scripts/ ./scripts/

# Copy configuration files
COPY config.ini .
COPY .env.example .

# Create necessary directories
RUN mkdir -p /app/logs

# Create non-root user
RUN useradd -m -u 1000 middleware && \
    chown -R middleware:middleware /app

# Make scripts executable
RUN chmod +x scripts/init.sh scripts/run.sh && \
    chown middleware:middleware scripts/init.sh scripts/run.sh

USER middleware

# Expose the port the app runs on
EXPOSE 5000

# Health check - updated to use the Flask app structure
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Use the init script as entrypoint
ENTRYPOINT ["./scripts/init.sh"]
