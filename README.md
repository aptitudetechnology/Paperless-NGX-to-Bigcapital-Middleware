*** Paperless-NGX to Bigcapital Middleware ***

A robust middleware solution that automatically imports financial documents (invoices and receipts) from Paperless-NGX into Bigcapital, streamlining your bookkeeping workflow.
Prerequisites

    Python 3.8+ (if running directly)
    Docker and Docker Compose (if using containerized deployment)
    Access to Paperless-NGX instance with API token
    Access to Bigcapital instance with API token

Paperless-NGX to Bigcapital Middleware

A middleware service that extracts data from documents in Paperless-NGX and syncs them to Bigcapital for accounting purposes. The extracted document data is stored in a PostgreSQL database for persistence and analysis.
Features (planned)

    🔄 Automatic document processing from Paperless-NGX
    💾 PostgreSQL database storage for extracted data
    🏷️ Tag-based document filtering and status tracking
    🌐 Web interface for monitoring and management
    🐳 Full Docker containerization
    📊 Processing statistics and error tracking
    🔗 Seamless Bigcapital integration


  # Folder Structure

```
paperless-bigcapital-middleware/
├── config/
│   ├── __init__.py
│   ├── settings.py          # Centralized configuration management
│   └── config.ini.example   # Template configuration file
├── core/
│   ├── __init__.py
│   ├── paperless_client.py  # Paperless-NGX API client
│   ├── bigcapital_client.py # BigCapital API client
│   └── processor.py         # Main processing logic
├── database/
│   ├── __init__.py
│   ├── models.py           # SQLAlchemy models
│   ├── connection.py       # Database connection management
│   └── migrations/         # Database schema files
│       └── 001_initial.sql
├── web/
│   ├── __init__.py
│   ├── app.py             # Flask application
│   ├── routes.py          # API endpoints and web routes
│   └── static/            # Static web assets
│       ├── css/
│       │   └── style.css
│       └── js/
├── utils/
│   ├── __init__.py
│   ├── logger.py          # Logging configuration
│   └── exceptions.py      # Custom exception classes
├── tests/
│   ├── __init__.py
│   ├── test_core.py       # Core functionality tests
│   ├── test_clients.py    # API client tests
│   └── test_database.py   # Database tests
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── scripts/
│   ├── init.sh           # Database initialization script
│   └── run.sh            # Application startup script
├── logs/                 # Application logs (created at runtime)
├── requirements.txt      # Python dependencies
├── config.ini           # Main configuration file
├── .env.example         # Environment variables template
├── .gitignore
└── README.md
```

## Directory Descriptions

### `/config/`
Configuration management and settings files.

### `/core/`
Core business logic and API client implementations.

### `/database/`
Database models, connections, and migration scripts.

### `/web/`
Web interface and API endpoints using Flask.

### `/utils/`
Utility functions, logging, and custom exceptions.

### `/tests/`
Unit tests and integration tests.

### `/docker/`
Docker configuration files for containerized deployment.

### `/scripts/`
Shell scripts for initialization and deployment.

### `/logs/`
Application log files (created automatically).


## 🧪 Testing Suite Folder Structure

The `tests/` directory houses the comprehensive test suite for the `paperless-bigcapital-middleware`. It's structured to provide clear separation and organization for different types of tests, ensuring robust coverage of the application's functionality.



### 📁 File Breakdown

- **`__init__.py`**  
  This empty file signals to Python that the `tests` directory is a package. This is crucial for `pytest` to properly discover and import test modules and shared fixtures.

- **`conftest.py`**  
  This special `pytest` file defines fixtures shared across multiple test files. It includes:
  - Flask app and client instances for web testing.
  - An in-memory SQLite database session for isolated database tests.
  - Reusable sample data objects (e.g., `ProcessedDocument`, `ProcessingError`) to streamline test setup.

- **`test_core.py`**  
  Contains unit tests for the core business logic, primarily focusing on `core/processor.py` and other central utilities. These tests isolate individual functions and classes, often using mocks for external dependencies.

- **`test_clients.py`**  
  Houses tests for the API clients (`core/paperless_client.py` and `core/bigcapital_client.py`). It focuses on verifying that your clients correctly construct HTTP requests and parse API responses, typically by mocking the actual network calls.

- **`test_database.py`**  
  Dedicated to testing your database models (`database/models.py`) and connection management (`database/connection.py`). It leverages the in-memory SQLite setup to ensure reliable data operations (Create, Read, Update, Delete) without affecting your development database.

- **`test_web.py`**  
  Tests the Flask web interface (`web/app.py`, `web/routes.py`). It simulates HTTP requests to your application's API endpoints, validating response status codes and data. Mocks are used to isolate the web layer from database and external API interactions.

- **`test_integration.py`**  
  Contains end-to-end integration tests that verify the complete document processing workflow. These tests confirm that different components of the middleware (e.g., fetching from Paperless-NGX, processing, sending to BigCapital, and database updates) interact correctly, often by running your Docker services and making real calls between them.



Architecture

Paperless-NGX → Middleware → PostgreSQL Database → Bigcapital

The middleware polls Paperless-NGX for new documents, extracts relevant data, stores it in PostgreSQL, and then creates corresponding entries in Bigcapital.
Quick Start with Docker (Recommended)
1. Clone and Setup

git clone <your-repo-url>
cd paperless-bigcapital-middleware

2. Configure Environment

Copy the example environment file and configure your settings:

cp .env.example .env

Edit .env with your actual values:

# Paperless-NGX Configuration
PAPERLESS_URL=http://paperless-ngx:8000
PAPERLESS_TOKEN=your-paperless-ngx-api-token

# Bigcapital Configuration  
BIGCAPITAL_URL=http://bigcapital:3000
BIGCAPITAL_TOKEN=your-bigcapital-api-token

# Database Configuration (defaults are fine for Docker setup)
DB_HOST=db
DB_PORT=5432
DB_NAME=middleware_db
DB_USER=middleware_user
DB_PASSWORD=middleware_password

3. Configure Application Settings

Edit config.ini to match your setup:

cp config.ini.example config.ini  # if you have a template
# OR edit the existing config.ini
nano config.ini

Key settings to update:

    Paperless-NGX URL and API token
    Bigcapital URL and API token
    Document filtering tags
    Processing intervals

4. Place Your Database Schema

Place your SQL initialization files in the db/ directory:

mkdir -p db/
# Copy your .sql files to the db/ directory
cp your-schema.sql db/
cp your-initial-data.sql db/

5. Build and Run

# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f paperless-bigcapital-middleware

# Check service status
docker-compose ps

6. Verify Installation

Check that all services are running:

# Check middleware health
curl http://localhost:5000/health

# Check database connection
docker-compose exec db psql -U middleware_user -d middleware_db -c "SELECT version();"

# View middleware logs
docker-compose logs paperless-bigcapital-middleware

Local Development Setup
1. Install Dependencies

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

2. Setup PostgreSQL

Install PostgreSQL locally or use Docker:

# Using Docker for PostgreSQL only
docker run -d \
  --name middleware-postgres \
  -e POSTGRES_DB=middleware_db \
  -e POSTGRES_USER=middleware_user \
  -e POSTGRES_PASSWORD=middleware_password \
  -p 5432:5432 \
  postgres:15-alpine

3. Initialize Database

# Run SQL files manually
psql -h localhost -U middleware_user -d middleware_db -f db/schema.sql
# Or use the provided script
./init.sh --setup-db-only

4. Configure and Run

# Copy and edit configuration
cp config.ini.example config.ini
nano config.ini

# Run the middleware
./run.sh

Configuration Reference
config.ini Sections
[paperless]

    url: Paperless-NGX instance URL
    token: API token for Paperless-NGX
    invoice_tags: Tags that identify invoice documents
    receipt_tags: Tags that identify receipt documents
    correspondents: Filter by specific correspondents (optional)

[bigcapital]

    url: Bigcapital instance URL
    token: API token for Bigcapital
    auto_create_customers: Automatically create customers if they don't exist
    default_due_days: Default days to add to invoice date for due date

[database]

    host: PostgreSQL host
    port: PostgreSQL port
    name: Database name
    user: Database user
    password: Database password
    pool_size: Connection pool size
    max_overflow: Maximum connection overflow
    pool_timeout: Connection timeout (seconds)
    pool_recycle: Connection recycle time (seconds)

[processing]

    processed_tag: Tag applied to successfully processed documents
    error_tag: Tag applied to documents with processing errors
    check_interval: How often to check for new documents (seconds)
    log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    batch_size: Number of documents to process in each batch
    max_retries: Maximum retry attempts for failed processing
    retry_delay: Delay between retry attempts (seconds)

[web_interface]

    host: Web interface host (0.0.0.0 for Docker)
    port: Web interface port
    secret_key: Flask secret key for sessions
    debug: Enable debug mode (development only)

Database Schema

The middleware creates several tables to store extracted data:

    documents: Document metadata from Paperless-NGX
    extracted_data: Extracted invoice/receipt data
    line_items: Individual line items from invoices
    processing_logs: Processing history and errors

API Endpoints

The middleware provides a web interface with the following endpoints:

    GET /: Dashboard with processing statistics
    GET /health: Health check endpoint
    GET /api/stats: Processing statistics (JSON)
    GET /api/documents: List processed documents
    POST /api/process: Trigger manual processing

Monitoring and Troubleshooting
View Logs

# Docker logs
docker-compose logs -f paperless-bigcapital-middleware

# Local logs
tail -f logs/middleware.log

Database Queries

# Connect to database
docker-compose exec db psql -U middleware_user -d middleware_db

# Check processing status
SELECT status, COUNT(*) FROM documents GROUP BY status;

# View recent documents
SELECT * FROM documents ORDER BY added_date DESC LIMIT 10;

Common Issues

    Database Connection Failed
        Check PostgreSQL is running: docker-compose ps
        Verify database credentials in config/env files
        Check network connectivity

    API Authentication Errors
        Verify API tokens in configuration
        Check service URLs are accessible
        Confirm API permissions

    Document Processing Stuck
        Check document tags match configuration
        Review processing logs for errors
        Verify Paperless-NGX document access

Updating
Update Docker Images

# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build

Update Database Schema

# Add new SQL files to db/ directory
# Restart services to apply changes
docker-compose restart paperless-bigcapital-middleware

Backup and Restore
Database Backup

# Create backup
docker-compose exec db pg_dump -U middleware_user middleware_db > backup.sql

# Restore backup
docker-compose exec -T db psql -U middleware_user middleware_db < backup.sql

Configuration Backup

# Backup configuration
cp config.ini config.ini.backup
cp .env .env.backup

Contributing

    Fork the repository
    Create a feature branch
    Make your changes
    Test thoroughly
    Submit a pull request

Support

For issues and questions:

    Check the logs for error messages
    Review the configuration settings
    Test database and API connectivity
    Create an issue with detailed information

License

GPL
