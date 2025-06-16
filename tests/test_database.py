"""Database tests for the paperless-bigcapital middleware."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

from database.models import Base, ProcessedDocument, ProcessingError, DocumentMapping
from database.connection import DatabaseConnection
from utils.exceptions import DatabaseError


class TestDatabaseConnection:
    """Test database connection management."""
    
    def test_get_connection_success(self, mock_db_config):
        """Test successful database connection."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_engine.return_value = MagicMock()
            
            db_conn = DatabaseConnection(mock_db_config)
            connection = db_conn.get_connection()
            
            assert connection is not None
            mock_engine.assert_called_once()
    
    def test_get_connection_failure(self, mock_db_config):
        """Test database connection failure."""
        with patch('database.connection.create_engine', side_effect=OperationalError("Connection failed", None, None)):
            db_conn = DatabaseConnection(mock_db_config)
            
            with pytest.raises(DatabaseError):
                db_conn.get_connection()
    
    def test_get_session_success(self, mock_db_config):
        """Test successful session creation."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_session_maker = MagicMock()
            mock_session = MagicMock()
            mock_session_maker.return_value = mock_session
            
            with patch('database.connection.sessionmaker', return_value=mock_session_maker):
                db_conn = DatabaseConnection(mock_db_config)
                session = db_conn.get_session()
                
                assert session == mock_session
    
    def test_close_connection(self, mock_db_config):
        """Test closing database connection."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.return_value = mock_connection
            
            db_conn = DatabaseConnection(mock_db_config)
            db_conn.get_connection()
            db_conn.close()
            
            mock_connection.dispose.assert_called_once()
    
    def test_context_manager(self, mock_db_config):
        """Test database connection as context manager."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.return_value = mock_connection
            
            with DatabaseConnection(mock_db_config) as db_conn:
                assert db_conn is not None
            
            mock_connection.dispose.assert_called_once()
    
    def test_health_check_success(self, mock_db_config):
        """Test successful database health check."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.return_value = mock_connection
            mock_connection.execute.return_value = None
            
            db_conn = DatabaseConnection(mock_db_config)
            result = db_conn.health_check()
            
            assert result is True
    
    def test_health_check_failure(self, mock_db_config):
        """Test failed database health check."""
        with patch('database.connection.create_engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.return_value = mock_connection
            mock_connection.execute.side_effect = OperationalError("Connection failed", None, None)
            
            db_conn = DatabaseConnection(mock_db_config)
            result = db_conn.health_check()
            
            assert result is False


class TestProcessedDocumentModel:
    """Test ProcessedDocument model."""
    
    def test_create_processed_document(self, db_session):
        """Test creating a processed document."""
        doc = ProcessedDocument(
            paperless_id=123,
            bigcapital_id="BC123",
            document_type="invoice",
            processing_status="completed",
            processed_at=datetime.utcnow()
        )
        
        db_session.add(doc)
        db_session.commit()
        
        assert doc.id is not None
        assert doc.paperless_id == 123
        assert doc.bigcapital_id == "BC123"
        assert doc.document_type == "invoice"
        assert doc.processing_status == "completed"
    
    def test_processed_document_repr(self, db_session):
        """Test ProcessedDocument string representation."""
        doc = ProcessedDocument(
            paperless_id=123,
            bigcapital_id="BC123",
            document_type="invoice"
        )
        
        expected = f"<ProcessedDocument(paperless_id=123, bigcapital_id='BC123', status='pending')>"
        assert repr(doc) == expected
    
    def test_processed_document_unique_constraint(self, db_session):
        """Test unique constraint on paperless_id."""
        doc1 = ProcessedDocument(
            paperless_id=123,
            document_type="invoice"
        )
        doc2 = ProcessedDocument(
            paperless_id=123,
            document_type="receipt"
        )
        
        db_session.add(doc1)
        db_session.commit()
        
        db_session.add(doc2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_processed_document_nullable_fields(self, db_session):
        """Test ProcessedDocument with nullable fields."""
        doc = ProcessedDocument(
            paperless_id=123,
            document_type="invoice"
        )
        
        db_session.add(doc)
        db_session.commit()
        
        assert doc.bigcapital_id is None
        assert doc.processing_status == "pending"
        assert doc.processed_at is None
        assert doc.error_message is None
    
    def test_processed_document_update_status(self, db_session):
        """Test updating document processing status."""
        doc = ProcessedDocument(
            paperless_id=123,
            document_type="invoice"
        )
        
        db_session.add(doc)
        db_session.commit()
        
        # Update status
        doc.processing_status = "completed"
        doc.bigcapital_id = "BC123"
        doc.processed_at = datetime.utcnow()
        
        db_session.commit()
        
        # Verify update
        updated_doc = db_session.query(ProcessedDocument).filter_by(paperless_id=123).first()
        assert updated_doc.processing_status == "completed"
        assert updated_doc.bigcapital_id == "BC123"
        assert updated_doc.processed_at is not None


class TestProcessingErrorModel:
    """Test ProcessingError model."""
    
    def test_create_processing_error(self, db_session):
        """Test creating a processing error."""
        error = ProcessingError(
            paperless_id=123,
            error_type="api_error",
            error_message="Failed to connect to BigCapital",
            retry_count=1,
            occurred_at=datetime.utcnow()
        )
        
        db_session.add(error)
        db_session.commit()
        
        assert error.id is not None
        assert error.paperless_id == 123
        assert error.error_type == "api_error"
        assert error.retry_count == 1
    
    def test_processing_error_repr(self, db_session):
        """Test ProcessingError string representation."""
        error = ProcessingError(
            paperless_id=123,
            error_type="api_error",
            error_message="Connection failed"
        )
        
        expected = f"<ProcessingError(paperless_id=123, type='api_error', retries=0)>"
        assert repr(error) == expected
    
    def test_processing_error_defaults(self, db_session):
        """Test ProcessingError default values."""
        error = ProcessingError(
            paperless_id=123,
            error_type="validation_error",
            error_message="Invalid data"
        )
        
        db_session.add(error)
        db_session.commit()
        
        assert error.retry_count == 0
        assert error.occurred_at is not None
        assert error.resolved is False
    
    def test_processing_error_increment_retry(self, db_session):
        """Test incrementing retry count."""
        error = ProcessingError(
            paperless_id=123,
            error_type="network_error",
            error_message="Timeout"
        )
        
        db_session.add(error)
        db_session.commit()
        
        # Increment retry count
        error.retry_count += 1
        db_session.commit()
        
        # Verify increment
        updated_error = db_session.query(ProcessingError).filter_by(paperless_id=123).first()
        assert updated_error.retry_count == 1
    
    def test_processing_error_resolve(self, db_session):
        """Test resolving a processing error."""
        error = ProcessingError(
            paperless_id=123,
            error_type="temporary_error",
            error_message="Service unavailable"
        )
        
        db_session.add(error)
        db_session.commit()
        
        # Resolve error
        error.resolved = True
        db_session.commit()
        
        # Verify resolution
        resolved_error = db_session.query(ProcessingError).filter_by(paperless_id=123).first()
        assert resolved_error.resolved is True


class TestDocumentMappingModel:
    """Test DocumentMapping model."""
    
    def test_create_document_mapping(self, db_session):
        """Test creating a document mapping."""
        mapping = DocumentMapping(
            paperless_document_type="invoice",
            bigcapital_document_type="bill",
            field_mappings={"title": "reference", "amount": "total"},
            is_active=True
        )
        
        db_session.add(mapping)
        db_session.commit()
        
        assert mapping.id is not None
        assert mapping.paperless_document_type == "invoice"
        assert mapping.bigcapital_document_type == "bill"
        assert mapping.field_mappings == {"title": "reference", "amount": "total"}
        assert mapping.is_active is True
    
    def test_document_mapping_repr(self, db_session):
        """Test DocumentMapping string representation."""
        mapping = DocumentMapping(
            paperless_document_type="receipt",
            bigcapital_document_type="expense"
        )
        
        expected = f"<DocumentMapping(paperless='receipt' -> bigcapital='expense')>"
        assert repr(mapping) == expected
    
    def test_document_mapping_unique_constraint(self, db_session):
        """Test unique constraint on document type mapping."""
        mapping1 = DocumentMapping(
            paperless_document_type="invoice",
            bigcapital_document_type="bill"
        )
        mapping2 = DocumentMapping(
            paperless_document_type="invoice",
            bigcapital_document_type="expense"
        )
        
        db_session.add(mapping1)
        db_session.commit()
        
        db_session.add(mapping2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_document_mapping_defaults(self, db_session):
        """Test DocumentMapping default values."""
        mapping = DocumentMapping(
            paperless_document_type="receipt",
            bigcapital_document_type="expense"
        )
        
        db_session.add(mapping)
        db_session.commit()
        
        assert mapping.field_mappings == {}
        assert mapping.is_active is True
        assert mapping.created_at is not None
        assert mapping.updated_at is not None
    
    def test_document_mapping_update_timestamp(self, db_session):
        """Test automatic timestamp update."""
        mapping = DocumentMapping(
            paperless_document_type="invoice",
            bigcapital_document_type="bill"
        )
        
        db_session.add(mapping)
        db_session.commit()
        
        original_updated_at = mapping.updated_at
        
        # Update mapping
        mapping.field_mappings = {"new_field": "new_value"}
        db_session.commit()
        
        # Verify timestamp update
        assert mapping.updated_at > original_updated_at


class TestDatabaseQueries:
    """Test database query operations."""
    
    def test_find_processed_document_by_paperless_id(self, db_session, sample_processed_document):
        """Test finding processed document by paperless ID."""
        db_session.add(sample_processed_document)
        db_session.commit()
        
        found_doc = db_session.query(ProcessedDocument).filter_by(
            paperless_id=sample_processed_document.paperless_id
        ).first()
        
        assert found_doc is not None
        assert found_doc.paperless_id == sample_processed_document.paperless_id
    
    def test_find_documents_by_status(self, db_session):
        """Test finding documents by processing status."""
        # Create documents with different statuses
        doc1 = ProcessedDocument(paperless_id=1, document_type="invoice", processing_status="pending")
        doc2 = ProcessedDocument(paperless_id=2, document_type="receipt", processing_status="completed")
        doc3 = ProcessedDocument(paperless_id=3, document_type="invoice", processing_status="pending")
        
        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()
        
        # Query pending documents
        pending_docs = db_session.query(ProcessedDocument).filter_by(processing_status="pending").all()
        
        assert len(pending_docs) == 2
        assert all(doc.processing_status == "pending" for doc in pending_docs)
    
    def test_find_failed_documents(self, db_session):
        """Test finding documents that failed processing."""
        # Create documents with different statuses
        doc1 = ProcessedDocument(paperless_id=1, document_type="invoice", processing_status="failed")
        doc2 = ProcessedDocument(paperless_id=2, document_type="receipt", processing_status="completed")
        
        db_session.add_all([doc1, doc2])
        db_session.commit()
        
        # Query failed documents
        failed_docs = db_session.query(ProcessedDocument).filter_by(processing_status="failed").all()
        
        assert len(failed_docs) == 1
        assert failed_docs[0].processing_status == "failed"
    
    def test_find_recent_errors(self, db_session):
        """Test finding recent processing errors."""
        # Create errors with different timestamps
        recent_error = ProcessingError(
            paperless_id=1,
            error_type="api_error",
            error_message="Recent error",
            occurred_at=datetime.utcnow()
        )
        old_error = ProcessingError(
            paperless_id=2,
            error_type="validation_error",
            error_message="Old error",
            occurred_at=datetime.utcnow() - timedelta(days=2)
        )
        
        db_session.add_all([recent_error, old_error])
        db_session.commit()
        
        # Query errors from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        recent_errors = db_session.query(ProcessingError).filter(
            ProcessingError.occurred_at > cutoff_time
        ).all()
        
        assert len(recent_errors) == 1
        assert recent_errors[0].error_message == "Recent error"
    
    def test_find_active_mappings(self, db_session):
        """Test finding active document mappings."""
        # Create active and inactive mappings
        active_mapping = DocumentMapping(
            paperless_document_type="invoice",
            bigcapital_document_type="bill",
            is_active=True
        )
        inactive_mapping = DocumentMapping(
            paperless_document_type="receipt",
            bigcapital_document_type="expense",
            is_active=False
        )
        
        db_session.add_all([active_mapping, inactive_mapping])
        db_session.commit()
        
        # Query active mappings
        active_mappings = db_session.query(DocumentMapping).filter_by(is_active=True).all()
        
        assert len(active_mappings) == 1
        assert active_mappings[0].paperless_document_type == "invoice"
    
    def test_count_processed_documents(self, db_session):
        """Test counting processed documents."""
        # Create test documents
        docs = [
            ProcessedDocument(paperless_id=i, document_type="invoice")
            for i in range(1, 6)
        ]
        
        db_session.add_all(docs)
        db_session.commit()
        
        # Count documents
        count = db_session.query(ProcessedDocument).count()
        
        assert count == 5
    
    def test_bulk_insert_documents(self, db_session):
        """Test bulk inserting documents."""
        # Create multiple documents
        docs = [
            ProcessedDocument(
                paperless_id=i,
                document_type="invoice",
                processing_status="pending"
            )
            for i in range(1, 11)
        ]
        
        # Bulk insert
        db_session.add_all(docs)
        db_session.commit()
        
        # Verify all documents were inserted
        count = db_session.query(ProcessedDocument).count()
        assert count == 10
    
    def test_update_document_status_bulk(self, db_session):
        """Test bulk updating document status."""
        # Create pending documents
        docs = [
            ProcessedDocument(paperless_id=i, document_type="invoice", processing_status="pending")
            for i in range(1, 6)
        ]
        
        db_session.add_all(docs)
        db_session.commit()
        
        # Bulk update status
        db_session.query(ProcessedDocument).filter_by(processing_status="pending").update({
            "processing_status": "processing"
        })
        db_session.commit()
        
        # Verify updates
        processing_docs = db_session.query(ProcessedDocument).filter_by(processing_status="processing").all()
        assert len(processing_docs) == 5


class TestDatabaseMigrations:
    """Test database migration functionality."""
    
    def test_create_tables(self, test_engine):
        """Test creating database tables."""
        # Create all tables
        Base.metadata.create_all(test_engine)
        
        # Verify tables exist
        inspector = create_engine(test_engine.url).connect()
        table_names = inspector.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in table_names]
        
        expected_tables = ['processed_documents', 'processing_errors', 'document_mappings']
        for table in expected_tables:
            assert table in table_names
        
        inspector.close()
    
    def test_drop_tables(self, test_engine):
        """Test dropping database tables."""
        # Create tables first
        Base.metadata.create_all(test_engine)
        
        # Drop all tables
        Base.metadata.drop_all(test_engine)
        
        # Verify tables don't exist
        inspector = create_engine(test_engine.url).connect()
        table_names = inspector.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in table_names]
        
        expected_tables = ['processed_documents', 'processing_errors', 'document_mappings']
        for table in expected_tables:
            assert table not in table_names
        
        inspector.close()


class TestDatabaseTransactions:
    """Test database transaction handling."""
    
    def test_transaction_commit(self, db_session):
        """Test successful transaction commit."""
        doc = ProcessedDocument(
            paperless_id=123,
            document_type="invoice"
        )
        
        db_session.add(doc)
        db_session.commit()
        
        # Verify document was saved
        saved_doc = db_session.query(ProcessedDocument).filter_by(paperless_id=123).first()
        assert saved_doc is not None
    
    def test_transaction_rollback(self, db_session):
        """Test transaction rollback on error."""
        doc1 = ProcessedDocument(paperless_id=123, document_type="invoice")
        doc2 = ProcessedDocument(paperless_id=123, document_type="receipt")  # Duplicate ID
        
        db_session.add(doc1)
        db_session.commit()
        
        # This should fail due to unique constraint
        db_session.add(doc2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        # Rollback the transaction
        db_session.rollback()
        
        # Verify only the first document exists
        docs = db_session.query(ProcessedDocument).all()
        assert len(docs) == 1
        assert docs[0].document_type == "invoice"
    
    def test_transaction_context_manager(self, db_session):
        """Test using database session as context manager."""
        try:
            with db_session.begin():
                doc = ProcessedDocument(
                    paperless_id=456,
                    document_type="receipt"
                )
                db_session.add(doc)
                # Transaction commits automatically
        except Exception:
            pass  # Transaction would rollback automatically
        
        # Verify document was saved
        saved_doc = db_session.query(ProcessedDocument).filter_by(paperless_id=456).first()
        assert saved_doc is not None


class TestDatabasePerformance:
    """Test database performance and optimization."""
    
    def test_query_performance_with_index(self, db_session):
        """Test query performance with indexed columns."""
        # Create many documents
        docs = [
            ProcessedDocument(
                paperless_id=i,
                document_type="invoice",
                processing_status="completed" if i % 2 == 0 else "pending"
            )
            for i in range(1, 1001)
        ]
        
        db_session.add_all(docs)
        db_session.commit()
        
        # Query by indexed paperless_id (should be fast)
        import time
        start_time = time.time()
        
        doc = db_session.query(ProcessedDocument).filter_by(paperless_id=500).first()
        
        query_time = time.time() - start_time
        
        assert doc is not None
        assert query_time < 0.1  # Should complete in less than 100ms
    
    def test_bulk_operations_performance(self, db_session):
        """Test performance of bulk database operations."""
        import time
        
        # Test bulk insert performance
        start_time = time.time()
        
        docs = [
            ProcessedDocument(paperless_id=i, document_type="invoice")
            for i in range(1, 501)
        ]
        
        db_session.add_all(docs)
        db_session.commit()
        
        insert_time = time.time() - start_time
        
        # Test bulk query performance
        start_time = time.time()
        
        all_docs = db_session.query(ProcessedDocument).all()
        
        query_time = time.time() - start_time
        
        assert len(all_docs) == 500
        assert insert_time < 1.0  # Bulk insert should complete in less than 1 second
        assert query_time < 0.5   # Bulk query should complete in less than 0.5 seconds
