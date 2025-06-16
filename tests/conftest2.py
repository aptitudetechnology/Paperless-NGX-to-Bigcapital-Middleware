#created by google gemini

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from web.app import create_app
from database.connection import DatabaseConnection
from database.models import Base, ProcessedDocument, ProcessingError, DocumentMapping

# Fixture for the Flask app
@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    app = create_app('testing') # 'testing' configuration
    with app.app_context():
        yield app

# Fixture for the Flask test client
@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()

# Fixture for an in-memory SQLite database session
@pytest.fixture(scope='function')
def db_session():
    """Create a new database session for each test that uses the database."""
    # Use an in-memory SQLite database for testing
    test_db_url = "sqlite:///:memory:"
    
    # Patch the DatabaseConnection to use the in-memory database
    with patch('database.connection.DatabaseConnection.get_session') as mock_get_session, \
         patch('database.connection.DatabaseConnection.engine') as mock_engine:
        
        # Configure a new engine and session for the in-memory database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(test_db_url)
        Session = sessionmaker(bind=engine)
        
        Base.metadata.create_all(engine) # Create tables
        session = Session()
        
        mock_engine.return_value = engine
        mock_get_session.return_value = session

        yield session

        session.close()
        Base.metadata.drop_all(engine) # Drop tables after test

# Sample data fixtures

@pytest.fixture
def sample_processed_document():
    """Returns a sample ProcessedDocument object."""
    doc = ProcessedDocument(
        paperless_id=123,
        bigcapital_id="BC-DOC-456",
        title="Test Document",
        processed_at=datetime.utcnow(),
        status="completed",
        checksum="abcdef12345"
    )
    # Mocking `to_dict` method for API response tests if it's not a real ORM instance
    doc.to_dict = lambda: {
        "id": getattr(doc, 'id', None), # id might be None for a new object not yet in db
        "paperless_id": doc.paperless_id,
        "bigcapital_id": doc.bigcapital_id,
        "title": doc.title,
        "processed_at": doc.processed_at.isoformat(),
        "status": doc.status,
        "checksum": doc.checksum
    }
    return doc

@pytest.fixture
def sample_processing_error():
    """Returns a sample ProcessingError object."""
    error = ProcessingError(
        paperless_id=124,
        error_message="Failed to connect to BigCapital API",
        timestamp=datetime.utcnow() - timedelta(hours=1),
        is_resolved=False
    )
    # Mocking `to_dict` method
    error.to_dict = lambda: {
        "id": getattr(error, 'id', 1), # Assign a mock ID for consistent testing
        "paperless_id": error.paperless_id,
        "error_message": error.error_message,
        "timestamp": error.timestamp.isoformat(),
        "is_resolved": error.is_resolved
    }
    return error

@pytest.fixture
def sample_document_mapping():
    """Returns a sample DocumentMapping object."""
    mapping = DocumentMapping(
        paperless_id=125,
        bigcapital_id="BC-MAP-789"
    )
    return mapping
