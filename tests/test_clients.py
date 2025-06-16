import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
import json
from requests.exceptions import RequestException, Timeout, ConnectionError

from core.paperless_client import PaperlessClient
from core.bigcapital_client import BigCapitalClient
from utils.exceptions import APIError, AuthenticationError, ValidationError


class TestPaperlessClient:
    """Test Paperless-NGX API client functionality."""
    
    @pytest.fixture
    def paperless_client(self, test_config):
        """Create PaperlessClient instance."""
        return PaperlessClient(
            base_url=test_config['PAPERLESS_BASE_URL'],
            api_token=test_config['PAPERLESS_API_TOKEN']
        )
    
    def test_client_initialization(self, paperless_client, test_config):
        """Test client initializes with correct configuration."""
        assert paperless_client.base_url == test_config['PAPERLESS_BASE_URL']
        assert paperless_client.api_token == test_config['PAPERLESS_API_TOKEN']
        assert paperless_client.session is not None
        
        # Check headers are set correctly
        expected_headers = {
            'Authorization': f'Token {test_config["PAPERLESS_API_TOKEN"]}',
            'Content-Type': 'application/json'
        }
        for header, value in expected_headers.items():
            assert paperless_client.session.headers[header] == value
    
    @patch('requests.Session.get')
    def test_get_document_success(self, mock_get, paperless_client, sample_paperless_document):
        """Test successful document retrieval."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_paperless_document
        mock_get.return_value = mock_response
        
        # Get document
        result = paperless_client.get_document(123)
        
        # Assertions
        assert result == sample_paperless_document
        mock_get.assert_called_once_with(
            f"{paperless_client.base_url}/api/documents/123/"
        )
    
    @patch('requests.Session.get')
    def test_get_document_not_found(self, mock_get, paperless_client):
        """Test handling document not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response
        
        with pytest.raises(APIError) as exc_info:
            paperless_client.get_document(999)
        
        assert "404" in str(exc_info.value)
    
    @patch('requests.Session.get')
    def test_get_document_unauthorized(self, mock_get, paperless_client):
        """Test handling unauthorized access."""
        mock_response = Mock()
        mock_response.status_
