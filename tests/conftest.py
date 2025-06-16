import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import Flask

# Import your application modules
from database.models import Base, ProcessedDocument, ProcessingStatus
from database.connection import DatabaseManager
from web.app import create_app
from config.settings import Config


@pytest.fixture(scope="session")
def test_config():
    """Create test configuration."""
    config = {
        'DATABASE_URL': 'sqlite:///:memory:',
        'PAPERLESS_BASE_URL': 'http://test-paperless.local',
        'PAPERLESS_API_TOKEN': 'test-paperless-token',
        'BIGCAPITAL_BASE_URL': 'http://test-bigcapital.local',
        'BIGCAPITAL_API_KEY': 'test-bigcapital-key',
        'BIGCAPITAL_TENANT_ID': 'test-tenant-id',
        'LOG_LEVEL': 'DEBUG',
        'RETRY_ATTEMPTS': 3,
        'RETRY_DELAY': 1
    }
    return config


@pytest.fixture(scope="session")
def test_db_engine(test_config):
    """Create test database engine."""
    engine = create_engine(test_config['DATABASE_URL'])
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_db_engine):
    """Create database session for tests."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def db_manager(test_config):
    """Create database manager for tests."""
    manager = DatabaseManager(test_config['DATABASE_URL'])
    manager.create_tables()
    yield manager
    manager.close()


@pytest.fixture
def flask_app(test_config):
    """Create Flask app for testing."""
    app = create_app(test_config)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def client(flask_app):
    """Create Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def app_context(flask_app):
    """Create Flask application context."""
    with flask_app.app_context():
        yield flask_app


# Mock data fixtures
@pytest.fixture
def sample_paperless_document():
    """Sample Paperless-NGX document data."""
    return {
        'id': 123,
        'title': 'Invoice_2024_001.pdf',
        'content': 'Invoice content with amount $1,500.00',
        'created': '2024-01-15T10:30:00Z',
        'modified': '2024-01-15T10:30:00Z',
        'correspondent': {
            'id': 1,
            'name': 'ACME Corp'
        },
        'document_type': {
            'id': 2,
            'name': 'Invoice'
        },
        'tags': [
            {'id': 1, 'name': 'expense'},
            {'id': 2, 'name': 'office'}
        ],
        'custom_fields': [
            {
                'field': {'id': 1, 'name': 'amount'},
                'value': '1500.00'
            },
            {
                'field': {'id': 2, 'name': 'vendor'},
                'value': 'ACME Corp'
            }
        ]
    }


@pytest.fixture
def sample_bigcapital_expense():
    """Sample BigCapital expense data."""
    return {
        'payee_id': 'vendor_123',
        'expense_account_id': 'account_456',
        'amount': 1500.00,
        'currency_code': 'USD',
        'expense_date': '2024-01-15',
        'reference': 'Invoice_2024_001',
        'description': 'Office expense from ACME Corp',
        'categories': [
            {
                'expense_account_id': 'account_456',
                'amount': 1500.00,
                'description': 'Office supplies'
            }
        ]
    }


@pytest.fixture
def sample_processed_document(db_session):
    """Create sample processed document in database."""
    doc = ProcessedDocument(
        paperless_document_id=123,
        bigcapital_expense_id='exp_789',
        status=ProcessingStatus.COMPLETED,
        metadata_={'title': 'Invoice_2024_001.pdf', 'amount': 1500.00}
    )
    db_session.add(doc)
    db_session.commit()
    return doc


# Mock response fixtures
@pytest.fixture
def mock_paperless_responses():
    """Mock responses from Paperless-NGX API."""
    return {
        'documents_list': {
            'count': 2,
            'results': [
                {
                    'id': 123,
                    'title': 'Invoice_2024_001.pdf',
                    'created': '2024-01-15T10:30:00Z'
                },
                {
                    'id': 124,
                    'title': 'Receipt_2024_002.pdf',
                    'created': '2024-01-16T14:20:00Z'
                }
            ]
        },
        'document_detail': {
            'id': 123,
            'title': 'Invoice_2024_001.pdf',
            'content': 'Invoice content',
            'created': '2024-01-15T10:30:00Z'
        }
    }


@pytest.fixture
def mock_bigcapital_responses():
    """Mock responses from BigCapital API."""
    return {
        'create_expense': {
            'id': 'exp_789',
            'reference': 'Invoice_2024_001',
            'amount': 1500.00,
            'status': 'active'
        },
        'vendors_list': {
            'vendors': [
                {
                    'id': 'vendor_123',
                    'display_name': 'ACME Corp'
                }
            ]
        },
        'accounts_list': {
            'accounts': [
                {
                    'id': 'account_456',
                    'name': 'Office Expenses',
                    'account_type': 'expense'
                }
            ]
        }
    }


# Test database data fixtures
@pytest.fixture
def populate_test_db(db_session):
    """Populate test database with sample data."""
    documents = [
        ProcessedDocument(
            paperless_document_id=1,
            bigcapital_expense_id='exp_001',
            status=ProcessingStatus.COMPLETED,
            metadata_={'title': 'Invoice_001.pdf'}
        ),
        ProcessedDocument(
            paperless_document_id=2,
            bigcapital_expense_id=None,
            status=ProcessingStatus.FAILED,
            metadata_={'title': 'Invoice_002.pdf'},
            error_message='API timeout'
        ),
        ProcessedDocument(
            paperless_document_id=3,
            status=ProcessingStatus.PENDING,
            metadata_={'title': 'Invoice_003.pdf'}
        )
    ]
    
    for doc in documents:
        db_session.add(doc)
    
    db_session.commit()
    return documents


# Environment setup fixtures
@pytest.fixture(autouse=True)
def setup_test_environment(test_config):
    """Setup test environment variables."""
    original_env = {}
    
    # Store original values
    for key, value in test_config.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = str(value)
    
    yield
    
    # Restore original values
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# Mock external services
@pytest.fixture
def mock_requests():
    """Mock requests library for API calls."""
    with patch('requests.Session') as mock_session:
        mock_instance = Mock()
        mock_session.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_paperless_client():
    """Mock Paperless-NGX client."""
    with patch('core.paperless_client.PaperlessClient') as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_bigcapital_client():
    """Mock BigCapital client."""
    with patch('core.bigcapital_client.BigCapitalClient') as mock_client:
        yield mock_client.return_value


# File handling fixtures
@pytest.fixture
def temp_config_file(test_config):
    """Create temporary configuration file."""
    config_content = """[paperless]
base_url = http://test-paperless.local
api_token = test-paperless-token

[bigcapital]
base_url = http://test-bigcapital.local
api_key = test-bigcapital-key
tenant_id = test-tenant-id

[database]
url = sqlite:///:memory:

[logging]
level = DEBUG
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(config_content)
        temp_file = f.name
    
    yield temp_file
    
    os.unlink(temp_file)


# Logging fixtures
@pytest.fixture
def capture_logs(caplog):
    """Capture application logs during tests."""
    import logging
    caplog.set_level(logging.DEBUG)
    yield caplog


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API test"
    )
    config.addinivalue_line(
        "markers", "database: mark test as database test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in item.name or "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add unit marker to unit tests
        if "unit" in item.name or "test_" in item.name:
            item.add_marker(pytest.mark.unit)
        
        # Add api marker to client tests
        if "client" in item.name or "api" in item.name:
            item.add_marker(pytest.mark.api)
        
        # Add database marker to database tests
        if "database" in item.name or "db" in item.name:
            item.add_marker(pytest.mark.database)
