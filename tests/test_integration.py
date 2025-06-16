
import pytest
import requests
import time
from unittest.mock import patch, MagicMock

# Assuming your Docker Compose services are named 'web', 'paperless', 'bigcapital', 'db'
# You might need to adjust these URLs based on your docker-compose.yml
WEB_APP_URL = "http://localhost:5000" # Or the appropriate host if running outside docker-compose test
PAPERLESS_API_URL = "http://localhost:8000/api" # Example, adjust based on your Paperless-NGX setup
BIGCAPITAL_API_URL = "http://localhost:9000/api" # Example, adjust based on your BigCapital mock

@pytest.mark.integration
class TestIntegrationWorkflow:
    """End-to-end integration tests for the middleware."""

    @pytest.fixture(scope="class", autouse=True)
    def wait_for_services(self):
        """Wait for the web app and dependent services to be ready."""
        # This fixture will ensure services are up before running integration tests.
        # In a real CI/CD pipeline, you'd have more robust health checks (e.g., docker-compose healthchecks)
        print("\nWaiting for web app to be ready...")
        retries = 30
        for i in range(retries):
            try:
                response = requests.get(f"{WEB_APP_URL}/health")
                if response.status_code == 200 and response.json().get('status') == 'healthy':
                    print("Web app is healthy.")
                    break
            except requests.exceptions.ConnectionError:
                pass
            print(f"Retrying in 1 second... ({i+1}/{retries})")
            time.sleep(1)
        else:
            pytest.fail("Web app did not become healthy in time.")

        # You might add similar checks for Paperless-NGX and BigCapital APIs
        # if they are part of your integration test scope and mocked for this test run.
        # For this example, we assume Paperless and BigCapital are either truly running
        # or robustly mocked if the middleware interacts with them during these tests.

    def test_e2e_document_processing_workflow(self, db_session):
        """
        Tests the end-to-end workflow:
        1. Mock a new document appearing in Paperless-NGX.
        2. Trigger the processing logic.
        3. Verify document is processed and sent to BigCapital (mocked).
        4. Verify database reflects the processed document.
        """
        paperless_doc_id = 999
        bigcapital_doc_id = "BC-INTEG-123"
        doc_title = "Integration Test Document"

        # Mock Paperless-NGX client to return a document
        with patch('core.paperless_client.PaperlessClient.get_document') as mock_get_document, \
             patch('core.bigcapital_client.BigCapitalClient.send_document') as mock_send_document:
            
            mock_get_document.return_value = {
                "id": paperless_doc_id,
                "title": doc_title,
                "content": "base64encodedpdfcontent",
                "checksum": "integration_checksum"
            }
            mock_send_document.return_value = {"id": bigcapital_doc_id, "status": "success"}

            # Simulate an event that triggers processing (e.g., a webhook call or scheduled task)
            # For this example, we directly call the processor.
            # In a real scenario, you might hit a Flask endpoint that triggers this.
            from core.processor import DocumentProcessor
            from config.settings import settings # Ensure settings can be loaded for testing

            processor = DocumentProcessor(settings=settings)
            
            # This would typically be called by a cron job or a webhook from Paperless
            # For integration test, we'll directly call the method that processes a single doc
            # Assuming processor has a method like process_single_document
            # If your processor works differently, adjust this part.
            result = processor.process_single_document(paperless_doc_id) 

            assert result is True # Or whatever success indicator your processor returns

            # Verify Paperless client was called
            mock_get_document.assert_called_once_with(paperless_doc_id)

            # Verify BigCapital client was called with transformed data
            mock_send_document.assert_called_once()
            args, kwargs = mock_send_document.call_args
            assert 'title' in args[0] and args[0]['title'] == doc_title

            # Verify database entry
            processed_doc = db_session.query(ProcessedDocument).filter_by(paperless_id=paperless_doc_id).first()
            assert processed_doc is not None
            assert processed_doc.bigcapital_id == bigcapital_doc_id
            assert processed_doc.status == "completed"
            assert processed_doc.checksum == "integration_checksum"
            
            # Verify no errors were logged for this successful processing
            error_entry = db_session.query(ProcessingError).filter_by(paperless_id=paperless_doc_id).first()
            assert error_entry is None

    def test_e2e_error_handling_and_retry(self, db_session, client):
        """
        Tests the error handling and retry workflow:
        1. Mock a document processing failure.
        2. Verify an error is logged in the database.
        3. Use the web API to trigger a retry.
        4. Mock successful reprocessing.
        5. Verify the error is marked as resolved and document is processed.
        """
        paperless_doc_id = 1000
        error_message = "Mock API connection error"
        reprocessed_bigcapital_id = "BC-RETRY-456"

        # Simulate initial failure
        with patch('core.paperless_client.PaperlessClient.get_document', return_value={"id": paperless_doc_id, "title": "Error Doc", "content": "mock", "checksum": "error_checksum"}), \
             patch('core.bigcapital_client.BigCapitalClient.send_document', side_effect=APIError(error_message)), \
             patch('database.connection.DatabaseConnection.get_session', return_value=db_session): # Ensure processor uses the test db session
            
            from core.processor import DocumentProcessor
            from config.settings import settings

            processor = DocumentProcessor(settings=settings)
            processor.process_single_document(paperless_doc_id)

        # Verify error logged
        error_entry = db_session.query(ProcessingError).filter_by(paperless_id=paperless_doc_id).first()
        assert error_entry is not None
        assert error_entry.error_message == error_message
        assert error_entry.is_resolved is False

        # Simulate retry via API
        with patch('core.paperless_client.PaperlessClient.get_document', return_value={"id": paperless_doc_id, "title": "Error Doc", "content": "mock", "checksum": "error_checksum"}), \
             patch('core.bigcapital_client.BigCapitalClient.send_document', return_value={"id": reprocessed_bigcapital_id, "status": "success"}), \
             patch('database.connection.DatabaseConnection.get_session', return_value=db_session): # Ensure web app uses the test db session
            
            response = client.post(f'/api/errors/{error_entry.id}/retry')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == 'Document reprocessing initiated.'

        # Verify error is now resolved and document processed
        re_checked_error = db_session.query(ProcessingError).filter_by(id=error_entry.id).first()
        assert re_checked_error.is_resolved is True

        reprocessed_doc = db_session.query(ProcessedDocument).filter_by(paperless_id=paperless_doc_id).first()
        assert reprocessed_doc is not None
        assert reprocessed_doc.bigcapital_id == reprocessed_bigcapital_id
        assert reprocessed_doc.status == "completed"
