#!/bin/bash
# Database initialization script for paperless-bigcapital middleware
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Paperless-Bigcapital Middleware Initialization${NC}"
echo "==============================================="

# Set working directory to project root
cd "$(dirname "$0")/.."

# Load environment variables if .env file exists
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading environment variables from .env...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default database connection parameters
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-middleware_user}
DB_PASSWORD=${DB_PASSWORD:-middleware_password}
DB_NAME=${DB_NAME:-middleware_db}

echo -e "${GREEN}Database connection details:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"
echo ""

# Wait for database to be ready
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
max_attempts=30
attempt=1

while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; do
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${RED}Database connection failed after $max_attempts attempts${NC}"
        exit 1
    fi
    
    echo "Attempt $attempt/$max_attempts: Waiting for database..."
    sleep 2
    attempt=$((attempt + 1))
done

echo -e "${GREEN}Database is ready!${NC}"

# Check if database exists and create if not
echo -e "${GREEN}Checking if database exists...${NC}"
if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${YELLOW}Database $DB_NAME does not exist. Creating...${NC}"
    PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
    echo -e "${GREEN}Database $DB_NAME created successfully!${NC}"
else
    echo -e "${GREEN}Database $DB_NAME already exists.${NC}"
fi

# Run database migrations
echo -e "${GREEN}Running database migrations...${NC}"
if [ -d "database/migrations" ] && [ "$(ls -A database/migrations/*.sql 2>/dev/null)" ]; then
    for migration_file in database/migrations/*.sql; do
        if [ -f "$migration_file" ]; then
            echo -e "${YELLOW}Running migration: $(basename "$migration_file")${NC}"
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"
        fi
    done
    echo -e "${GREEN}Database migrations completed!${NC}"
else
    echo -e "${YELLOW}No SQL migration files found in database/migrations/${NC}"
fi

# Initialize database using Python models (if available)
echo -e "${GREEN}Initializing database schema...${NC}"
if [ -f "database/models.py" ] && [ -f "database/connection.py" ]; then
    python -c "
import sys
sys.path.append('.')
try:
    from database.connection import init_database
    init_database()
    print('Database schema initialized successfully')
except Exception as e:
    print(f'Database schema initialization failed: {e}')
    # Don't exit here as migrations might have handled it
    " || echo -e "${YELLOW}Python database initialization failed or skipped${NC}"
fi

# Create logs directory
echo -e "${GREEN}Creating logs directory...${NC}"
mkdir -p logs
chmod 755 logs

# Verify configuration
echo -e "${GREEN}Verifying configuration...${NC}"
if [ ! -f "config.ini" ]; then
    if [ -f "config/config.ini.example" ]; then
        echo -e "${YELLOW}Creating config.ini from example...${NC}"
        cp config/config.ini.example config.ini
        echo -e "${RED}Please edit config.ini with your API tokens before starting the middleware.${NC}"
    else
        echo -e "${RED}No configuration file found. Please create config.ini${NC}"
        exit 1
    fi
fi

# Test database connection with application
echo -e "${GREEN}Testing application database connection...${NC}"
python -c "
import sys
sys.path.append('.')
try:
    from database.connection import get_database_connection
    conn = get_database_connection()
    if conn:
        print('Application database connection successful!')
        conn.close()
    else:
        print('Application database connection failed!')
        sys.exit(1)
except Exception as e:
    print(f'Application database connection test failed: {e}')
    sys.exit(1)
" || {
    echo -e "${RED}Application database connection test failed${NC}"
    exit 1
}

echo -e "${GREEN}Initialization completed successfully!${NC}"
echo ""
echo -e "${GREEN}Starting the middleware application...${NC}"

# Start the application
exec ./scripts/run.sh "$@"
