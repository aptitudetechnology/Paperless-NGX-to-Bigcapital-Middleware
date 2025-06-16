import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

from core.processor import DocumentProcessor
from core.paperless_client import PaperlessClient
from core.bigcapital_client import BigCapitalClient
from database.models import ProcessedDocument, ProcessingStatus
from utils.exceptions import ProcessingError, APIError, ValidationError


class TestDocumentProcessor:
    """Test the core document processing functionality."""
    
    @pytest.fixture
    def processor(self, test_config, db_manager):
        """Create DocumentProcessor instance."""
        return DocumentProcessor(config=test_config, db_manager=db_manager)
    
    def test_processor_initialization(self, processor, test_config):
        """Test processor initializes correctly."""
        assert processor.config == test_config
        assert processor.db_manager is not None
        assert hasattr(processor, 'paperless_client')
        assert hasattr(processor, 'bigcapital_client')
    
    @patch('core.processor.PaperlessClient')
    @patch('core.processor.BigCapitalClient')
    def test_process_document_success(self, mock_bc_client, mock_pl_client, 
                                    processor, sample_paperless_document, 
                                    sample_bigcapital_expense, db_session):
        """Test successful document processing."""
        # Setup mocks
        mock_pl_client.return_value.get_document.return_value = sample_paperless_document
        mock_bc_client.return_value.create_expense.return_value = {'id': 'exp_789'}
        
        # Process document
        result = processor.process_document(123)
        
        # Assertions
        assert result is not None
        assert result['status'] == 'success'
        assert 'expense_id' in result
        
        # Verify database record
        processed_doc = db_session.query(ProcessedDocument).filter_by(
            paperless_document_id=123
        ).first()
        assert processed_doc is not None
        assert processed_doc.status == ProcessingStatus.COMPLETED
    
    def test_process_document_already_processed(self, processor, db_session,
                                              sample_processed_document):
        """Test processing already processed document."""
        # Document already exists in database
        result = processor.process_document(123)
        
        assert result['status'] == 'skipped'
        assert 'already processed' in result['message'].lower()
    
    @patch('core.processor.PaperlessClient')
    def test_process_document_paperless_error(self, mock_pl_client, processor):
        """Test handling Paperless-NGX API errors."""
        mock_pl_client.return_value.get_document.side_effect = APIError("API Error")
        
        with pytest.raises(ProcessingError):
            processor.process_document(123)
    
    @patch('core.processor.PaperlessClient')
    @patch('core.processor.BigCapitalClient')
    def test_process_document_bigcapital_error(self, mock_bc_client, mock_pl_client,
                                             processor, sample_paperless_document):
        """Test handling BigCapital API errors."""
        mock_pl_client.return_value.get_document.return_value = sample_paperless_document
        mock_bc_client.return_value.create_expense.side_effect = APIError("BC API Error")
        
        with pytest.raises(ProcessingError):
            processor.process_document(123)
    
    def test_transform_document_to_expense(self, processor, sample_paperless_document):
        """Test document transformation logic."""
        expense_data = processor._transform_document_to_expense(sample_paperless_document)
        
        assert expense_data is not None
        assert 'amount' in expense_data
        assert 'reference' in expense_data
        assert 'description' in expense_data
        assert expense_data['reference'] == 'Invoice_2024_001.pdf'
    
    def test_extract_amount_from_content(self, processor):
        """Test amount extraction from document content."""
        test_cases = [
            ("Total: $1,500.00", 1500.00),
            ("Amount: €2,350.50", 2350.50),
            ("Invoice for £999.99", 999.99),
            ("Cost: 1234.56 USD", 1234.56),
            ("No amount here", None)
        ]
        
        for content, expected in test_cases:
            result = processor._extract_amount_from_content(content)
            assert result == expected
    
    def test_extract_vendor_from_document(self, processor, sample_paperless_document):
        """Test vendor extraction from document."""
        vendor = processor._extract_vendor_from_document(sample_paperless_document)
        assert vendor == 'ACME Corp'
    
    def test_categorize_expense(self, processor):
        """Test expense categorization logic."""
        test_cases = [
            (["office", "supplies"], "office_expenses"),
            (["travel", "transport"], "travel_expenses"),
            (["utilities", "phone"], "utilities"),
            (["unknown"], "general_expenses")
        ]
        
        for tags, expected_category in test_cases:
            mock_doc = {'tags': [{'name': tag} for tag in tags]}
            category = processor._categorize_expense(mock_doc)
            assert category == expected_category
    
    def test_validate_document_data(self, processor):
        """Test document data validation."""
        # Valid document
        valid_doc = {
            'id': 123,
            'title': 'test.pdf',
            'content': 'Valid content with $100.00'
        }
        assert processor._validate_document_data(valid_doc) is True
        
        # Invalid documents
        invalid_docs = [
            {},  # Empty
            {'id': 123},  # Missing title
            {'id': 123, 'title': ''},  # Empty title
            {'id': 123, 'title': 'test.pdf', 'content': ''},  # Empty content
        ]
        
        for invalid_doc in invalid_docs:
            with pytest.raises(ValidationError):
                processor._validate_document_data(invalid_doc)
    
    @patch('core.processor.PaperlessClient')
    def test_batch_process_documents(self, mock_pl_client, processor):
        """Test batch processing multiple documents."""
        # Mock document list response
        mock_pl_client.return_value.get_unprocessed_documents.return_value = [
            {'id': 1, 'title': 'doc1.pdf'},
            {'id': 2, 'title': 'doc2.pdf'},
            {'id': 3, 'title': 'doc3.pdf'}
        ]
        
        with patch.object(processor, 'process_document') as mock_process:
            mock_process.return_value = {'status': 'success'}
            
            results = processor.batch_process_documents(limit=5)
            
            assert len(results) == 3
            assert mock_process.call_count == 3
    
    def test_retry_logic(self, processor, test_config):
        """Test retry logic for failed operations."""
        with patch.object(processor, '_perform_api_call') as mock_call:
            # Simulate failures then success
            mock_call.side_effect = [
                APIError("Temporary error"),
                APIError("Another error"),
                {'success': True}
            ]
            
            result = processor._retry_operation(processor._perform_api_call, "test")
            
            assert result == {'success': True}
            assert mock_call.call_count == 3
    
    def test_retry_exhaustion(self, processor):
        """Test behavior when all retry attempts are exhausted."""
        with patch.object(processor, '_perform_api_call') as mock_call:
            mock_call.side_effect = APIError("Persistent error")
            
            with pytest.raises(ProcessingError):
                processor._retry_operation(processor._perform_api_call, "test")
    
    def test_update_processing_status(self, processor, db_session):
        """Test updating document processing status."""
        # Create initial record
        doc = ProcessedDocument(
            paperless_document_id=999,
            status=ProcessingStatus.PENDING
        )
        db_session.add(doc)
        db_session.commit()
        
        # Update status
        processor._update_processing_status(
            999, 
            ProcessingStatus.COMPLETED,
            bigcapital_expense_id='exp_123'
        )
        
        # Verify update
        updated_doc = db_session.query(ProcessedDocument).filter_by(
            paperless_document_id=999
        ).first()
        
        assert updated_doc.status == ProcessingStatus.COMPLETED
        assert updated_doc.bigcapital_expense_id == 'exp_123'
        assert updated_doc.processed_at is not None
    
    def test_get_processing_statistics(self, processor, populate_test_db):
        """Test getting processing statistics."""
        stats = processor.get_processing_statistics()
        
        assert 'total_documents' in stats
        assert 'completed' in stats
        assert 'failed' in stats
        assert 'pending' in stats
        
        assert stats['total_documents'] == 3
        assert stats['completed'] == 1
        assert stats['failed'] == 1
        assert stats['pending'] == 1


class TestDocumentTransformation:
    """Test document transformation utilities."""
    
    def test_clean_title(self):
        """Test document title cleaning."""
        from core.processor import clean_title
        
        test_cases = [
            ("Invoice_2024_001.pdf", "Invoice 2024 001"),
            ("Receipt-with-dashes.PDF", "Receipt with dashes"),
            ("Document___with___underscores.txt", "Document with underscores"),
            ("UPPERCASE_TITLE.pdf", "UPPERCASE TITLE")
        ]
        
        for input_title, expected in test_cases:
            result = clean_title(input_title)
            assert result == expected
    
    def test_parse_date_string(self):
        """Test date string parsing."""
        from core.processor import parse_date_string
        
        test_cases = [
            ("2024-01-15T10:30:00Z", datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)),
            ("2024-01-15", datetime(2024, 1, 15)),
            ("invalid-date", None)
        ]
        
        for date_str, expected in test_cases:
            result = parse_date_string(date_str)
            if expected:
                assert result.replace(tzinfo=None) == expected.replace(tzinfo=None)
            else:
                assert result is None
    
    def test_extract_currency_from_content(self):
        """Test currency extraction from content."""
        from core.processor import extract_currency_from_content
        
        test_cases = [
            ("Amount: $1,500.00", "USD"),
            ("Total: €2,350.50", "EUR"),
            ("Cost: £999.99", "GBP"),
            ("Price: ¥50000", "JPY"),
            ("No currency symbol", "USD")  # Default
        ]
        
        for content, expected in test_cases:
            result = extract_currency_from_content(content)
            assert result == expected


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_processing_error_creation(self):
        """Test ProcessingError exception."""
        error = ProcessingError("Test error", document_id=123)
        
        assert str(error) == "Test error"
        assert error.document_id == 123
        assert error.timestamp is not None
    
    def test_api_error_with_response(self):
        """Test APIError with response data."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        error = APIError("API failed", response=mock_response)
        
        assert error.status_code == 400
        assert error.response_text == "Bad Request"
    
    def test_validation_error_details(self):
        """Test ValidationError with field details."""
        error = ValidationError("Validation failed", field="amount", value="invalid")
        
        assert error.field == "amount"
        assert error.value == "invalid"


@pytest.mark.integration
class TestDocumentProcessorIntegration:
    """Integration tests for document processor."""
    
    @pytest.fixture
    def integration_processor(self, test_config, db_manager):
        """Create processor for integration tests."""
        return DocumentProcessor(config=test_config, db_manager=db_manager)
    
    @patch('requests.Session.get')
    @patch('requests.Session.post')
    def test_end_to_end_processing(self, mock_post, mock_get, integration_processor,
                                 sample_paperless_document, mock_bigcapital_responses):
        """Test complete end-to-end document processing."""
        # Mock Paperless-NGX response
        mock_get.return_value.json.return_value = sample_paperless_document
        mock_get.return_value.status_code = 200
        
        # Mock BigCapital response
        mock_post.return_value.json.return_value = mock_bigcapital_responses['create_expense']
        mock_post.return_value.status_code = 201
        
        # Process document
        result = integration_processor.process_document(123)
        
        # Verify successful processing
        assert result['status'] == 'success'
        assert 'expense_id' in result
        
        # Verify API calls
        assert mock_get.called
        assert mock_post.called
    
    def test_concurrent_processing(self, integration_processor):
        """Test concurrent document processing."""
        import threading
        import time
        
        results = []
        errors = []
        
        def process_doc(doc_id):
            try:
                with patch.object(integration_processor, 'process_document') as mock_process:
                    mock_process.return_value = {'status': 'success', 'doc_id': doc_id}
                    result = integration_processor.process_document(doc_id)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=process_doc, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 5
        assert len(errors) == 0
    
    @pytest.mark.slow
    def test_large_batch_processing(self, integration_processor):
        """Test processing large batch of documents."""
        document_ids = list(range(1, 101))  # 100 documents
        
        with patch.object(integration_processor, 'process_document') as mock_process:
            mock_process.return_value = {'status': 'success'}
            
            results = integration_processor.batch_process_documents(
                document_ids=document_ids,
                batch_size=10
            )
            
            assert len(results) == 100
            assert all(r['status'] == 'success' for r in results)
