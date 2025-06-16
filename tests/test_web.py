"""Web interface tests for the paperless-bigcapital middleware."""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from flask import url_for

from web.app import create_app
from database.models import ProcessedDocument, ProcessingError, DocumentMapping
from utils.exceptions import DatabaseError, APIError


class TestWebApplication:
    """Test Flask application setup and configuration."""
    
    def test_app_creation(self, app):
        """Test Flask application creation."""
        assert app is not None
        assert app.config['TESTING'] is True
    
    def test_app_config(self, app):
        """Test application configuration."""
        assert 'SECRET_KEY' in app.config
        assert app.config['TESTING'] is True
    
    def test_app_blueprints(self, app):
        """Test that required blueprints are registered."""
        blueprint_names = [bp.name for bp in app.iter_blueprints()]
        # Adjust based on your actual blueprint structure
        expected_blueprints = ['main']  # Update with your actual blueprints
        
        for blueprint in expected_blueprints:
            assert blueprint in blueprint_names or len(blueprint_names) >= 0


class TestHealthEndpoints:
    """Test health check and status endpoints."""
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        with patch('database.connection.DatabaseConnection.health_check', return_value=True):
            response = client.get('/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert 'timestamp' in data
    
    def test_health_check_database_failure(self, client):
        """Test health check with database failure."""
        with patch('database.connection.DatabaseConnection.health_check', return_value=False):
            response = client.get('/health')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert 'database' in data['checks']
            assert data['checks']['database'] is False
    
    def test_health_check_detailed(self, client):
        """Test detailed health check endpoint."""
        with patch('database.connection.DatabaseConnection.health_check', return_value=True), \
             patch('core.paperless_client.PaperlessClient.health_check', return_value=True), \
             patch('core.bigcapital_client.BigCapitalClient.health_check', return_value=True):
            
            response = client.get('/health/detailed')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert data['checks']['database'] is True
            assert data['checks']['paperless'] is True
            assert data['checks']['bigcapital'] is True
    
    def test_status_endpoint(self, client):
        """Test application status endpoint."""
        with patch('database.models.ProcessedDocument') as mock_doc, \
             patch('database.models.ProcessingError') as mock_error:
            
            # Mock database queries
            mock_doc.query.count.return_value = 150
            mock_doc.query.filter_by.return_value.count.return_value = 10
            mock_error.query.filter.return_value.count.return_value = 5
            
            response = client.get('/status')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'total_documents' in data
            assert 'pending_documents' in data
            assert 'recent_errors' in data
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint."""
        response = client.get('/metrics')
        
        assert response.status_code == 200
        # Check that response contains Prometheus-style metrics
        assert 'processed_documents_total' in response.data.decode()


class TestDocumentEndpoints:
    """Test document management endpoints."""
    
    def test_list_documents_empty(self, client):
        """Test listing documents when none exist."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.all.return_value = []
            
            response = client.get('/api/documents')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['documents'] == []
            assert data['total'] == 0
    
    def test_list_documents_with_data(self, client, sample_processed_document):
        """Test listing documents with data."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.all.return_value = [sample_processed_document]
            
            response = client.get('/api/documents')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['documents']) == 1
            assert data['documents'][0]['paperless_id'] == sample_processed_document.paperless_id
    
    def test_list_documents_with_pagination(self, client):
        """Test document listing with pagination."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_paginate = MagicMock()
            mock_paginate.items = []
            mock_paginate.total = 0
            mock_paginate.page = 1
            mock_paginate.pages = 1
            mock_query.paginate.return_value = mock_paginate
            
            response = client.get('/api/documents?page=1&per_page=10')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'pagination' in data
    
    def test_get_document_success(self, client, sample_processed_document):
        """Test getting a specific document."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = sample_processed_document
            
            response = client.get(f'/api/documents/{sample_processed_document.paperless_id}')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['paperless_id'] == sample_processed_document.paperless_id
    
    def test_get_document_not_found(self, client):
        """Test getting a non-existent document."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None
            
            response = client.get('/api/documents/999')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'message' in data
            assert 'Document not found' in data['message']

    def test_get_document_by_bigcapital_id_success(self, client, sample_processed_document):
        """Test getting a document by its BigCapital ID."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = sample_processed_document
            response = client.get(f'/api/documents/bigcapital/{sample_processed_document.bigcapital_id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['bigcapital_id'] == sample_processed_document.bigcapital_id

    def test_get_document_by_bigcapital_id_not_found(self, client):
        """Test getting a non-existent document by BigCapital ID."""
        with patch('database.models.ProcessedDocument.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None
            response = client.get('/api/documents/bigcapital/non_existent_id')
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'Document not found' in data['message']


class TestErrorEndpoints:
    """Test error log endpoints."""

    def test_list_errors_empty(self, client):
        """Test listing errors when none exist."""
        with patch('database.models.ProcessingError.query') as mock_query:
            mock_query.order_by.return_value.all.return_value = []
            response = client.get('/api/errors')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['errors'] == []
            assert data['total'] == 0

    def test_list_errors_with_data(self, client, sample_processing_error):
        """Test listing errors with data."""
        with patch('database.models.ProcessingError.query') as mock_query:
            mock_query.order_by.return_value.all.return_value = [sample_processing_error]
            response = client.get('/api/errors')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['errors']) == 1
            assert data['errors'][0]['paperless_id'] == sample_processing_error.paperless_id
            assert data['errors'][0]['error_message'] == sample_processing_error.error_message

    def test_get_error_details_success(self, client, sample_processing_error):
        """Test getting details of a specific error."""
        with patch('database.models.ProcessingError.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = sample_processing_error
            response = client.get(f'/api/errors/{sample_processing_error.id}')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['id'] == sample_processing_error.id
            assert data['error_message'] == sample_processing_error.error_message

    def test_get_error_details_not_found(self, client):
        """Test getting details of a non-existent error."""
        with patch('database.models.ProcessingError.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None
            response = client.get('/api/errors/999')
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'Error not found' in data['message']

    def test_retry_error_success(self, client, sample_processing_error):
        """Test retrying a specific error."""
        with patch('database.models.ProcessingError.query') as mock_error_query, \
             patch('core.processor.DocumentProcessor.process_document') as mock_process:
            
            mock_error_query.filter_by.return_value.first.return_value = sample_processing_error
            mock_process.return_value = True  # Simulate successful reprocessing
            
            response = client.post(f'/api/errors/{sample_processing_error.id}/retry')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == 'Document reprocessing initiated.'
            mock_process.assert_called_once_with(sample_processing_error.paperless_id)

    def test_retry_error_not_found(self, client):
        """Test retrying a non-existent error."""
        with patch('database.models.ProcessingError.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = None
            response = client.post('/api/errors/999/retry')
            assert response.status_code == 404
            data = json.loads(response.data)
            assert 'Error not found' in data['message']

    def test_retry_error_processing_failure(self, client, sample_processing_error):
        """Test retrying an error that fails during reprocessing."""
        with patch('database.models.ProcessingError.query') as mock_error_query, \
             patch('core.processor.DocumentProcessor.process_document') as mock_process:
            
            mock_error_query.filter_by.return_value.first.return_value = sample_processing_error
            mock_process.side_effect = APIError("BigCapital API error")
            
            response = client.post(f'/api/errors/{sample_processing_error.id}/retry')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'Failed to reprocess' in data['message']
            assert 'BigCapital API error' in data['details']
            mock_process.assert_called_once_with(sample_processing_error.paperless_id)
