#!/usr/bin/env python3
"""
Paperless-NGX to Bigcapital Middleware - Routes
"""
import os
from flask import Blueprint, jsonify, request, render_template
from datetime import datetime
import logging
from functools import wraps

# Import your custom modules
try:
    from database.models import ProcessedDocument, ProcessingLog
    from database.connection import get_db_session
    from core.processor import DocumentProcessor
    from utils.logger import get_logger
except ImportError:
    # Fallback for development
    ProcessedDocument = None
    ProcessingLog = None
    get_db_session = None
    DocumentProcessor = None
    get_logger = None

# Create blueprints for different route groups
api_bp = Blueprint('api', __name__, url_prefix='/api')
web_bp = Blueprint('web', __name__)

# Setup logging
if get_logger:
    logger = get_logger('routes')
else:
    logger = logging.getLogger('routes')

def require_auth(f):
    """Authentication decorator for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE']:
            api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            expected_key = os.environ.get('API_KEY')
            if expected_key and api_key != expected_key:
                return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def handle_errors(f):
    """Error handling decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e) if os.environ.get('FLASK_ENV') == 'development' else 'An error occurred'
            }), 500
    return decorated_function

# =============================================================================
# API Routes
# =============================================================================

@api_bp.route('/stats')
@handle_errors
def stats():
    """Get processing statistics."""
    stats = get_processing_stats()
    return jsonify(stats)

@api_bp.route('/documents')
@handle_errors
def documents():
    """List processed documents with pagination and filtering."""
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 100)
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '').strip()
    
    documents, total = get_documents(
        page=page, 
        per_page=per_page, 
        status=status_filter,
        search=search_query
    )
    
    return jsonify({
        'documents': documents,
        'total': total,
        'page': page,
        'per_page': per_page,
        'has_next': (page * per_page) < total,
        'has_prev': page > 1,
        'filters': {
            'status': status_filter,
            'search': search_query
        }
    })

@api_bp.route('/documents/<int:document_id>')
@handle_errors
def document_detail(document_id):
    """Get detailed information about a specific document."""
    document = get_document_by_id(document_id)
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(document)

@api_bp.route('/process', methods=['POST'])
@require_auth
@handle_errors
def process():
    """Trigger manual processing."""
    data = request.get_json() if request.is_json else {}
    force = data.get('force', False)
    document_id = data.get('document_id')
    batch_size = data.get('batch_size', 10)
    
    if DocumentProcessor:
        processor = DocumentProcessor()
        if document_id:
            result = processor.process_document(document_id, force=force)
            message = f"Processing document {document_id}"
        else:
            result = processor.process_all(force=force, batch_size=batch_size)
            message = f"Processing documents in batches of {batch_size}"
        
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

@api_bp.route('/process/<int:document_id>', methods=['POST'])
@require_auth
@handle_errors
def process_document(document_id):
    """Process a specific document."""
    data = request.get_json() if request.is_json else {}
    force = data.get('force', False)
    
    if DocumentProcessor:
        processor = DocumentProcessor()
        result = processor.process_document(document_id, force=force)
        
        return jsonify({
            'message': f'Processing document {document_id}',
            'document_id': document_id,
            'status': 'started',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result
        })
    else:
        return jsonify({
            'message': f'Processing document {document_id} (simulated)',
            'document_id': document_id,
            'status': 'simulated',
            'timestamp': datetime.utcnow().isoformat()
        })

@api_bp.route('/logs')
@handle_errors
def logs():
    """Get processing logs with pagination and filtering."""
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 100)
    level = request.args.get('level')
    document_id = request.args.get('document_id')
    
    logs, total = get_logs(
        page=page, 
        per_page=per_page, 
        level=level,
        document_id=document_id
    )
    
    return jsonify({
        'logs': logs,
        'total': total,
        'page': page,
        'per_page': per_page,
        'filters': {
            'level': level,
            'document_id': document_id
        }
    })

@api_bp.route('/config')
@handle_errors
def config():
    """Get current configuration (non-sensitive values only)."""
    config = {
        'paperless_url': os.environ.get('PAPERLESS_URL', 'Not configured'),
        'bigcapital_url': os.environ.get('BIGCAPITAL_URL', 'Not configured'),
        'database_host': os.environ.get('DB_HOST', 'localhost'),
        'database_name': os.environ.get('DB_NAME', 'middleware_db'),
        'check_interval': int(os.environ.get('CHECK_INTERVAL', '300')),
        'batch_size': int(os.environ.get('BATCH_SIZE', '10')),
        'max_retries': int(os.environ.get('MAX_RETRIES', '3')),
        'version': '1.0.0',
        'debug': os.environ.get('FLASK_ENV') == 'development',
        'features': {
            'database_available': get_db_session is not None,
            'processor_available': DocumentProcessor is not None,
            'authentication_enabled': bool(os.environ.get('API_KEY'))
        }
    }
    return jsonify(config)

@api_bp.route('/health')
@handle_errors
def health():
    """Detailed health check for API."""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'paperless-bigcapital-middleware',
        'version': '1.0.0',
        'components': {}
    }
    
    # Check database connection
    if get_db_session:
        try:
            session = get_db_session()
            session.execute("SELECT 1")
            session.close()
            health_status['components']['database'] = {
                'status': 'healthy',
                'message': 'Database connection successful'
            }
        except Exception as e:
            health_status['components']['database'] = {
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}'
            }
            health_status['status'] = 'degraded'
    else:
        health_status['components']['database'] = {
            'status': 'not_configured',
            'message': 'Database module not available'
        }
    
    # Check processor availability
    if DocumentProcessor:
        health_status['components']['processor'] = {
            'status': 'available',
            'message': 'Document processor ready'
        }
    else:
        health_status['components']['processor'] = {
            'status': 'not_available',
            'message': 'Document processor not loaded'
        }
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

# =============================================================================
# Web Routes
# =============================================================================

@web_bp.route('/')
@handle_errors
def dashboard():
    """Main dashboard."""
    stats = get_processing_stats()
    recent_logs = get_recent_logs(limit=10)
    recent_documents = get_recent_documents(limit=10)
    
    return render_template('dashboard.html',
                         stats=stats,
                         recent_logs=recent_logs,
                         recent_documents=recent_documents,
                         timestamp=datetime.utcnow())

@web_bp.route('/documents')
@handle_errors
def documents_page():
    """Documents listing page."""
    page = int(request.args.get('page', 1))
    per_page = 25
    status_filter = request.args.get('status')
    
    documents, total = get_documents(page=page, per_page=per_page, status=status_filter)
    
    return render_template('documents.html',
                         documents=documents,
                         total=total,
                         page=page,
                         per_page=per_page,
                         status_filter=status_filter,
                         has_next=(page * per_page) < total,
                         has_prev=page > 1)

@web_bp.route('/logs')
@handle_errors
def logs_page():
    """Logs viewing page."""
    page = int(request.args.get('page', 1))
    per_page = 50
    level = request.args.get('level')
    
    logs, total = get_logs(page=page, per_page=per_page, level=level)
    
    return render_template('logs.html',
                         logs=logs,
                         total=total,
                         page=page,
                         per_page=per_page,
                         level=level,
                         has_next=(page * per_page) < total,
                         has_prev=page > 1)

# =============================================================================
# Helper Functions
# =============================================================================

def get_processing_stats():
    """Get processing statistics from database."""
    if not get_db_session or not ProcessedDocument:
        return {
            'total_documents': total,
            'processed_documents': processed,
            'failed_documents': failed,
            'pending_documents': pending,
            'last_run': last_run,
            'status': 'operational',
            'processing_rate': round(processing_rate, 2),
            'error_rate': round(error_rate, 2)
        }
    except Exception as e:
        logger.error(f"Error getting processing stats: {e}")
        return {
            'total_documents': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'pending_documents': 0,
            'last_run': None,
            'status': 'error',
            'error': str(e),
            'processing_rate': 0,
            'error_rate': 0
        }

def get_documents(page=1, per_page=50, status=None, search=None):
    """Get paginated list of documents with optional filtering."""
    if not get_db_session or not ProcessedDocument:
        return [], 0
    
    try:
        session = get_db_session()
        query = session.query(ProcessedDocument)
        
        # Apply filters
        if status:
            query = query.filter_by(status=status)
        
        if search:
            query = query.filter(ProcessedDocument.title.ilike(f'%{search}%'))
        
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
                'document_type': getattr(doc, 'document_type', 'unknown'),
                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                'error_message': doc.error_message,
                'bigcapital_id': getattr(doc, 'bigcapital_id', None),
                'retry_count': getattr(doc, 'retry_count', 0)
            })
        
        session.close()
        return doc_list, total
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return [], 0

def get_document_by_id(document_id):
    """Get detailed information about a specific document."""
    if not get_db_session or not ProcessedDocument:
        return None
    
    try:
        session = get_db_session()
        doc = session.query(ProcessedDocument).filter_by(id=document_id).first()
        
        if not doc:
            session.close()
            return None
        
        # Get related logs
        logs = []
        if ProcessingLog:
            doc_logs = session.query(ProcessingLog).filter_by(document_id=document_id).order_by(ProcessingLog.created_at.desc()).all()
            logs = [{
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at.isoformat() if log.created_at else None
            } for log in doc_logs]
        
        document_data = {
            'id': doc.id,
            'paperless_id': doc.paperless_id,
            'title': doc.title,
            'status': doc.status,
            'document_type': getattr(doc, 'document_type', 'unknown'),
            'created_at': doc.created_at.isoformat() if doc.created_at else None,
            'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
            'error_message': doc.error_message,
            'bigcapital_id': getattr(doc, 'bigcapital_id', None),
            'retry_count': getattr(doc, 'retry_count', 0),
            'extracted_data': getattr(doc, 'extracted_data', {}),
            'logs': logs
        }
        
        session.close()
        return document_data
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        return None

def get_logs(page=1, per_page=50, level=None, document_id=None):
    """Get paginated processing logs with optional filtering."""
    if not get_db_session or not ProcessingLog:
        return [], 0
    
    try:
        session = get_db_session()
        query = session.query(ProcessingLog)
        
        # Apply filters
        if level:
            query = query.filter_by(level=level)
        
        if document_id:
            query = query.filter_by(document_id=document_id)
        
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
                'document_id': log.document_id,
                'component': getattr(log, 'component', 'system')
            })
        
        session.close()
        return log_list, total
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return [], 0

def get_recent_logs(limit=5):
    """Get recent processing logs for dashboard."""
    logs, _ = get_logs(page=1, per_page=limit)
    return logs

def get_recent_documents(limit=5):
    """Get recently processed documents for dashboard."""
    documents, _ = get_documents(page=1, per_page=limit)
    return documents'total_documents': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'pending_documents': 0,
            'last_run': None,
            'status': 'no_database',
            'processing_rate': 0,
            'error_rate': 0
        }
    
    try:
        session = get_db_session()
        
        # Get document counts by status
        total = session.query(ProcessedDocument).count()
        processed = session.query(ProcessedDocument).filter_by(status='processed').count()
        failed = session.query(ProcessedDocument).filter_by(status='failed').count()
        pending = session.query(ProcessedDocument).filter_by(status='pending').count()
        
        # Calculate rates
        processing_rate = (processed / total * 100) if total > 0 else 0
        error_rate = (failed / total * 100) if total > 0 else 0
        
        # Get last processing time
        last_doc = session.query(ProcessedDocument).order_by(ProcessedDocument.processed_at.desc()).first()
        last_run = last_doc.processed_at.isoformat() if last_doc and last_doc.processed_at else None
        
        session.close()
        
        return {
