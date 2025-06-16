# Flask application
#!/usr/bin/env python3
"""
Paperless-NGX to Bigcapital Middleware - Flask Application
"""

import os
import sys
from flask import Flask, jsonify, render_template_string
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'paperless-bigcapital-middleware'
        }), 200
    
    # Dashboard endpoint
    @app.route('/')
    def dashboard():
        """Simple dashboard for the middleware."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Paperless-NGX to Bigcapital Middleware</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { padding: 20px; background: #f0f8ff; border-radius: 5px; }
                .endpoint { margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 3px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Paperless-NGX to Bigcapital Middleware</h1>
                <div class="status">
                    <h2>Status: Running</h2>
                    <p>Middleware service is operational.</p>
                    <p>Timestamp: {{ timestamp }}</p>
                </div>
                
                <h2>Available Endpoints:</h2>
                <div class="endpoint">
                    <strong>GET /health</strong> - Health check endpoint
                </div>
                <div class="endpoint">
                    <strong>GET /api/stats</strong> - Processing statistics
                </div>
                <div class="endpoint">
                    <strong>GET /api/documents</strong> - List processed documents
                </div>
                <div class="endpoint">
                    <strong>POST /api/process</strong> - Trigger manual processing
                </div>
            </div>
        </body>
        </html>
        """
        return render_template_string(html_template, timestamp=datetime.utcnow().isoformat())
    
    # API endpoints placeholder
    @app.route('/api/stats')
    def api_stats():
        """Get processing statistics."""
        return jsonify({
            'total_documents': 0,
            'processed_documents': 0,
            'failed_documents': 0,
            'last_run': None,
            'status': 'ready'
        })
    
    @app.route('/api/documents')
    def api_documents():
        """List processed documents."""
        return jsonify({
            'documents': [],
            'total': 0,
            'page': 1,
            'per_page': 50
        })
    
    @app.route('/api/process', methods=['POST'])
    def api_process():
        """Trigger manual processing."""
        return jsonify({
            'message': 'Processing triggered',
            'status': 'started',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    return app

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    # Get configuration from environment
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # Run the application
    app.run(host=host, port=port, debug=debug)
