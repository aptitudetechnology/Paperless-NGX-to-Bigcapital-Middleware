#!/usr/bin/env python3
"""
Paperless-NGX to Bigcapital Middleware - Flask Application
"""
import os
import sys
from flask import Flask, jsonify, render_template, request, send_from_directory
from datetime import datetime, timedelta
import logging
from functools import wraps

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your custom modules (these will be created/imported as needed)
try:
    from database.models import ProcessedDocument, ProcessingLog
    from database.connection import get_db_session
    from core.processor import DocumentProcessor
    from utils.logger import get_logger
except ImportError:
    # Fallback for development when modules aren't ready yet
    ProcessedDocument = None
    ProcessingLog = None
    get_db_session = None
    DocumentProcessor = None
    get_logger = None

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'
    app.config['WEB_HOST'] = os.environ.get('WEB_HOST', '0.0.0.0')
    app.config['WEB_PORT'] = int(os.environ.get('WEB_PORT', 5000))
    
    # Setup logging
    if get_logger:
        logger = get_logger('web')
    else:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('web')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    # Authentication decorator (basic - you can enhance this)
    def require_auth(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # For now, just check if API key is provided for API endpoints
            if request.path.startswith('/api/') and request.method in ['POST', 'PUT', 'DELETE']:
                api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
                expected_key = os.environ.get('API_KEY')
                if expected_key and api_key != expected_key:
                    return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    # Static files
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory(app.static_folder, filename)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'paperless-bigcapital-middleware',
            'version': '1.0.0'
        }
        
        # Check database connection if available
        if get_db_session:
            try:
                session = get_db_session()
                # Simple query to test connection
                session.execute("SELECT 1")
                session.close()
                health_status['database'] = 'connected'
            except Exception as e:
                health_status['database'] = 'disconnected'
                health_status['database_error'] = str(e)
                health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
    
    # Dashboard endpoint
    @app.route('/')
    def dashboard():
        """Main dashboard for the middleware."""
        try:
            # Get basic stats
            stats = get_processing_stats()
            recent_logs = get_recent_logs(limit=5)
            
            return render_template('dashboard.html', 
                                 stats=stats, 
                                 recent_logs=recent_logs,
                                 timestamp=datetime.utcnow())
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")
            # Fallback to simple HTML if template fails
            return render_template_string(get_simple_dashboard_template(), 
                                        timestamp=datetime.utcnow().isoformat())
    
    # API Stats endpoint
    @app.route('/api/stats')
    def api_stats():
        """Get processing statistics."""
        try:
            stats = get_processing_stats()
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return jsonify({
                'error': 'Unable to retrieve stats',
                'total_documents': 0,
                'processed_documents': 0,
                'failed_documents': 0,
                'last_run': None,
                'status': 'error'
            }), 500
    
    # API Documents endpoint
    @app.route('/api/documents')
    def api_documents():
        """List processed documents."""
        try:
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('per_page', 50)), 100)  # Max 100 per page
            status_filter = request.args.get('status')
            
            documents, total = get_documents(page=page, per_page=per_page, status=status_filter)
            
            return jsonify({
                'documents': documents,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_next': (page * per_page) < total,
                'has_prev': page > 1
            })
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            return jsonify({
                'error': 'Unable to retrieve documents',
                'documents': [],
                'total': 0
            }), 500
    
    # API Process endpoint
    @app.route('/api/process', methods=['POST'])
    @require_auth
    def api_process():
        """Trigger manual processing."""
        try:
            # Get optional parameters
            force = request.json.get('force', False) if request.is_json else False
            document_id = request.json.get('document_id') if request.is_json else None
            
            if DocumentProcessor:
                processor = DocumentProcessor()
                if document_id:
                    result = processor.process_document(document_id, force=force)
                    message = f"Processing document {document_id}"
                else:
                    result = processor.process_all(force=force)
                    message = "Processing all documents"
                
                return jsonify({
                    'message': message,
                    'status': 'started',
                    'timestamp': datetime.utcnow().isoformat(),
                    'result': result
                })
            else:
                return jsonify({
                    'message': 'Processing triggered (processor not available)',
                    'status': 'simulated',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error triggering processing: {e}")
            return jsonify({
                'error': 'Processing failed to start',
                'message': str(e)
            }), 500
    
    # API Logs endpoint
    @app.route('/api/logs')
    def api_logs():
        """Get processing logs."""
        try:
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('per_page', 50)), 100)
            level = request.args.get('level')  # Filter by log level
            
            logs, total = get_logs(page=page, per_page=per_page, level=level)
            
            return jsonify({
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page
            })
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return jsonify({
                'error': 'Unable to retrieve logs',
                'logs': []
            }), 500
    
    # Configuration endpoint
    @app.route('/api/config')
    def api_config():
        """Get current configuration (non-sensitive)."""
        try:
            config = {
                'paperless_url': os.environ.get('PAPERLESS_URL', 'Not configured'),
                'bigcapital_url': os.environ.get('BIGCAPITAL_URL', 'Not configured'),
                'database_host': os.environ.get('DB_HOST', 'localhost'),
                'check_interval': os.environ.get('CHECK_INTERVAL', '300'),
                'batch_size': os.environ.get('BATCH_SIZE', '10'),
                'version': '1.0.0',
                'debug': app.config.get('DEBUG', False)
            }
            return jsonify(config)
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return jsonify({'error': 'Unable to retrieve configuration'}), 500
    
    return app

def get_processing_stats():
    """Get processing statistics from database."""
    if not get_db_session or not ProcessedDocument:
        return {
            'total_documents': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'pending_documents': 0,
            'last_run': None,
            'status': 'no_database'
        }
    
    try:
        session = get_db_session()
        
        # Get document counts by status
        total = session.query(ProcessedDocument).count()
        processed = session.query(ProcessedDocument).filter_by(status='processed').count()
        failed = session.query(ProcessedDocument).filter_by(status='failed').count()
        pending = session.query(ProcessedDocument).filter_by(status='pending').count()
        
        # Get last processing time
        last_doc = session.query(ProcessedDocument).order_by(ProcessedDocument.processed_at.desc()).first()
        last_run = last_doc.processed_at.isoformat() if last_doc and last_doc.processed_at else None
        
        session.close()
        
        return {
            'total_documents': total,
            'processed_documents': processed,
            'failed_documents': failed,
            'pending_documents': pending,
            'last_run': last_run,
            'status': 'operational'
        }
    except Exception as e:
        return {
            'total_documents': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'pending_documents': 0,
            'last_run': None,
            'status': 'error',
            'error': str(e)
        }

def get_documents(page=1, per_page=50, status=None):
    """Get paginated list of documents."""
    if not get_db_session or not ProcessedDocument:
        return [], 0
    
    try:
        session = get_db_session()
        query = session.query(ProcessedDocument)
        
        if status:
            query = query.filter_by(status=status)
        
        total = query.count()
        documents = query.order_by(ProcessedDocument.created_at.desc())\
                        .offset((page - 1) * per_page)\
                        .limit(per_page)\
                        .all()
        
        doc_list = []
        for doc in documents:
            doc_list.append({
                'id': doc.id,
                'paperless_id': doc.paperless_id,
                'title': doc.title,
                'status': doc.status,
                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                'error_message': doc.error_message
            })
        
        session.close()
        return doc_list, total
    except Exception:
        return [], 0

def get_logs(page=1, per_page=50, level=None):
    """Get paginated processing logs."""
    if not get_db_session or not ProcessingLog:
        return [], 0
    
    try:
        session = get_db_session()
        query = session.query(ProcessingLog)
        
        if level:
            query = query.filter_by(level=level)
        
        total = query.count()
        logs = query.order_by(ProcessingLog.created_at.desc())\
                   .offset((page - 1) * per_page)\
                   .limit(per_page)\
                   .all()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at.isoformat() if log.created_at else None,
                'document_id': log.document_id
            })
        
        session.close()
        return log_list, total
    except Exception:
        return [], 0

def get_recent_logs(limit=5):
    """Get recent processing logs for dashboard."""
    logs, _ = get_logs(page=1, per_page=limit)
    return logs

def get_simple_dashboard_template():
    """Fallback dashboard template."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Paperless-NGX to Bigcapital Middleware</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { border-bottom: 2px solid #007bff; padding-bottom: 15px; margin-bottom: 30px; }
            .status { padding: 20px; background: #e8f4fd; border-radius: 5px; margin-bottom: 20px; }
            .endpoint { margin: 10px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }
            .card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            h1 { color: #007bff; margin: 0; }
            h2 { color: #333; margin-top: 0; }
            .healthy { color: #28a745; }
            .timestamp { color: #6c757d; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Paperless-NGX to Bigcapital Middleware</h1>
                <p class="timestamp">Last updated: {{ timestamp }}</p>
            </div>
            
            <div class="status">
                <h2>Status: <span class="healthy">Running</span></h2>
                <p>Middleware service is operational and ready to process documents.</p>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h2>🔗 API Endpoints</h2>
                    <div class="endpoint">
                        <strong>GET /health</strong><br>
                        Health check endpoint for monitoring
                    </div>
                    <div class="endpoint">
                        <strong>GET /api/stats</strong><br>
                        Processing statistics and metrics
                    </div>
                    <div class="endpoint">
                        <strong>GET /api/documents</strong><br>
                        List processed documents with pagination
                    </div>
                    <div class="endpoint">
                        <strong>POST /api/process</strong><br>
                        Trigger manual document processing
                    </div>
                    <div class="endpoint">
                        <strong>GET /api/logs</strong><br>
                        View processing logs and errors
                    </div>
                </div>
                
                <div class="card">
                    <h2>📊 Quick Stats</h2>
                    <p>Database connection required for detailed statistics.</p>
                    <p>Configure your database connection and restart the service.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    # Get configuration from environment
    host = os.environ.get('WEB_HOST', '0.0.0.0')
    port = int(os.environ.get('WEB_PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"Starting Paperless-NGX to Bigcapital Middleware Web Interface...")
    print(f"Server: http://{host}:{port}")
    print(f"Debug mode: {debug}")
    
    # Run the application
    app.run(host=host, port=port, debug=debug)
