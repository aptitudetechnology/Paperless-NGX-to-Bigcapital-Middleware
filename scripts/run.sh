#!/bin/bash
# Script to run the middleware with PostgreSQL support
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Paperless-Bigcapital Middleware Setup${NC}"
echo "========================================"

# Set working directory to project root
cd "$(dirname "$0")/.."

# Check if virtual environment exists (only for local development)
if [ ! -f "/.dockerenv" ] && [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment (only for local development)
if [ ! -f "/.dockerenv" ] && [ -d "venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Install dependencies (only for local development)
if [ ! -f "/.dockerenv" ]; then
    echo -e "${GREEN}Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Check if config file exists
if [ ! -f "config.ini" ]; then
    echo -e "${RED}Config file not found.${NC}"
    if [ -f "config/config.ini.example" ]; then
        echo -e "${YELLOW}Creating config.ini from example...${NC}"
        cp config/config.ini.example config.ini
    else
        echo -e "${YELLOW}Creating default config.ini...${NC}"
        cat > config.ini << EOF
[paperless]
url = http://localhost:8000
token = your-paperless-ngx-api-token
invoice_tags = invoice,bill,accounts-receivable
receipt_tags = receipt,payment
correspondents = 

[bigcapital]
url = http://localhost:3000
token = your-bigcapital-api-token
auto_create_customers = true
default_due_days = 30

[database]
host = localhost
port = 5432
name = middleware_db
user = middleware_user
password = middleware_password
pool_size = 5
max_overflow = 10
pool_timeout = 30
pool_recycle = 3600

[processing]
processed_tag = bc-processed
error_tag = bc-error
check_interval = 300
log_level = INFO
batch_size = 10
max_retries = 3
retry_delay = 60

[web_interface]
host = 0.0.0.0
port = 5000
secret_key = your-secret-key-here
debug = false
EOF
    fi
    echo -e "${RED}Please edit config.ini with your API tokens and database settings.${NC}"
    exit 1
fi

# Check if .env file exists and load it
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading environment variables from .env...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check database connection
echo -e "${GREEN}Checking database connection...${NC}"
if command -v psql >/dev/null 2>&1; then
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    DB_USER=${DB_USER:-middleware_user}
    DB_NAME=${DB_NAME:-middleware_db}
    
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        echo -e "${GREEN}Database connection successful!${NC}"
    else
        echo -e "${YELLOW}Warning: Cannot connect to database. Make sure PostgreSQL is running.${NC}"
        echo "Database connection details:"
        echo "  Host: $DB_HOST"
        echo "  Port: $DB_PORT"
        echo "  User: $DB_USER"
        echo "  Database: $DB_NAME"
        echo ""
        echo -e "${YELLOW}You can start PostgreSQL with Docker using:${NC}"
        echo "  docker-compose up middleware-db"
        echo ""
        echo -e "${YELLOW}Or install and start PostgreSQL locally.${NC}"
    fi
else
    echo -e "${YELLOW}PostgreSQL client not found. Database connection check skipped.${NC}"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Initialize database if needed
echo -e "${GREEN}Checking database initialization...${NC}"
if [ -f "database/connection.py" ]; then
    python -c "
import sys
sys.path.append('.')
try:
    from database.connection import init_database
    init_database()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    exit(1)
    " || echo -e "${YELLOW}Database initialization skipped or failed${NC}"
fi

# Run the middleware using the new Flask app structure
echo -e "${GREEN}Starting paperless-bigcapital middleware...${NC}"

# Check if we're running in Docker or locally
if [ -f "/.dockerenv" ]; then
    # Running in Docker container
    echo -e "${GREEN}Running in Docker container...${NC}"
    export FLASK_APP=web.app:app
    export FLASK_ENV=${FLASK_ENV:-production}
    python -m flask run --host=0.0.0.0 --port=5000
else
    # Running locally
    echo -e "${GREEN}Running locally...${NC}"
    export FLASK_APP=web.app:app
    export FLASK_ENV=${FLASK_ENV:-development}
    
    # Check if we should run Flask directly or the processor
    if [ "$1" = "--processor-only" ]; then
        echo -e "${GREEN}Starting processor only...${NC}"
        python -m core.processor "$@"
    elif [ "$1" = "--web-only" ]; then
        echo -e "${GREEN}Starting web interface only...${NC}"
        python -m flask run --host=0.0.0.0 --port=5000 --debug
    else
        echo -e "${GREEN}Starting full middleware (web + processor)...${NC}"
        # You might want to run both the web interface and processor
        # This could be done with background processes or separate terminals
        python -m web.app "$@"
    fi
fi
