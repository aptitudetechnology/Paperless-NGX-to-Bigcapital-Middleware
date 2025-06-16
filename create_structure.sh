#!/bin/bash

# Paperless-NGX to BigCapital Middleware - Folder Structure Creation Script
# This script creates the MVP folder structure for the middleware project

set -e  # Exit on any error

echo "Creating Paperless-NGX to BigCapital Middleware folder structure..."

# Create main directories
echo "Creating directories..."
mkdir -p config
mkdir -p core
mkdir -p database/migrations
mkdir -p web/static/css
mkdir -p web/static/js
mkdir -p utils
mkdir -p tests
mkdir -p docker
mkdir -p scripts
mkdir -p logs

# Create config files
echo "Creating config files..."
touch config/__init__.py
touch config/settings.py
touch config/config.ini.example

# Create core files
echo "Creating core files..."
touch core/__init__.py
touch core/paperless_client.py
touch core/bigcapital_client.py
touch core/processor.py

# Create database files
echo "Creating database files..."
touch database/__init__.py
touch database/models.py
touch database/connection.py
touch database/migrations/001_initial.sql

# Create web files
echo "Creating web files..."
touch web/__init__.py
touch web/app.py
touch web/routes.py
touch web/static/css/style.css
touch web/static/js/.gitkeep

# Create utils files
echo "Creating utils files..."
touch utils/__init__.py
touch utils/logger.py
touch utils/exceptions.py

# Create test files
echo "Creating test files..."
touch tests/__init__.py
touch tests/test_core.py
touch tests/test_clients.py
touch tests/test_database.py

# Create docker files
echo "Creating docker files..."
touch docker/Dockerfile
touch docker/docker-compose.yml

# Create script files
echo "Creating script files..."
touch scripts/init.sh
touch scripts/run.sh

# Create root level files
echo "Creating root level files..."
touch requirements.txt
touch config.ini
touch .env.example
touch .gitignore

# Make scripts executable
echo "Making scripts executable..."
chmod +x scripts/init.sh
chmod +x scripts/run.sh

# Create a basic .gitignore
echo "Creating basic .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
env/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/*.log
*.log

# Environment variables
.env

# Database
*.db
*.sqlite3

# Configuration (keep examples)
config.ini
!config.ini.example

# Docker
docker-compose.override.yml
EOF

# Create a basic requirements.txt
echo "Creating basic requirements.txt..."
cat > requirements.txt << 'EOF'
# Core dependencies
Flask==2.3.3
SQLAlchemy==2.0.23
psycopg2-binary==2.9.9
requests==2.31.0
python-dotenv==1.0.0
configparser==6.0.0

# Development dependencies
pytest==7.4.3
pytest-flask==1.3.0
pytest-cov==4.1.0
black==23.11.0
flake8==6.1.0

# Optional dependencies
gunicorn==21.2.0
python-json-logger==2.0.7
EOF

# Create logs directory placeholder
touch logs/.gitkeep

echo ""
echo "✅ Folder structure created successfully!"
echo ""
echo "📁 Project structure:"
echo "   - config/          Configuration management"
echo "   - core/            Business logic and API clients"
echo "   - database/        Database models and migrations"
echo "   - web/             Flask web interface"
echo "   - utils/           Utility functions and logging"
echo "   - tests/           Unit and integration tests"
echo "   - docker/          Docker configuration"
echo "   - scripts/         Shell scripts"
echo "   - logs/            Application logs"
echo ""
echo "🚀 Next steps:"
echo "   1. Review and customize config/config.ini.example"
echo "   2. Set up your .env file based on .env.example"
echo "   3. Install dependencies: pip install -r requirements.txt"
echo "   4. Initialize your database with scripts/init.sh"
echo ""
echo "Happy coding! 🎉"
EOF
