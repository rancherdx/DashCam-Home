import logging
import os

from flask import (Flask, jsonify, render_template, send_from_directory,
                   current_app, request)

import subprocess
from backend.camera_manager import CameraManager
from backend.stream_processor import StreamProcessor
from backend.onvif_controller import ONVIFController
from backend.recording_manager import RecordingManager
from frontend.api_routes import create_api_routes
from config import SNAPSHOTS_DIR, CLIPS_DIR, THUMBNAILS_DIR, HLS_OUTPUT_DIR, LOGS_DIR

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(LOGS_DIR, "app.log"))
        ]
    )


def check_ffmpeg() -> bool:
    """Checks if FFmpeg is installed and accessible."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Setup logging
setup_logging()


def create_app():
    app = Flask(__name__)

    # Configuration
    def str_to_bool(val):
        return val.lower() in ('true', '1', 'yes')

    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'API_TOKEN': os.environ.get('API_TOKEN', 'dev-api-token-change-in-production'),
        'CLOUDFLARE_TUNNEL': str_to_bool(os.environ.get('CLOUDFLARE_TUNNEL', 'False')),
        'CLOUDFLARE_DOMAIN': os.environ.get('CLOUDFLARE_DOMAIN', ''),
    })

    # Initialize components
    app.stream_processor = StreamProcessor(cloudflare_enabled=app.config['CLOUDFLARE_TUNNEL'])
    app.onvif_controller = ONVIFController()
    app.camera_manager = CameraManager(
        stream_processor=app.stream_processor,
        onvif_controller=app.onvif_controller
    )
    app.recording_manager = RecordingManager(SNAPSHOTS_DIR, CLIPS_DIR, THUMBNAILS_DIR)

    # Wire up circular dependencies
    app.camera_manager.recording_manager = app.recording_manager
    app.recording_manager.camera_manager = app.camera_manager

    # Register API routes
    api_blueprint = create_api_routes(
        app.camera_manager,
        app.stream_processor,
        app.onvif_controller,
        app.recording_manager
    )
    app.register_blueprint(api_blueprint, url_prefix='/api')

    @app.after_request
    def add_security_headers(response):
        """Add security headers for all responses"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        if request.is_secure or current_app.config.get('CLOUDFLARE_TUNNEL', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        if request.path.startswith('/streams/'):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

        return response

    # Frontend routes
    @app.route('/')
    def dashboard():
        cameras = app.camera_manager.get_all_cameras()
        return render_template('dashboard.html', cameras=cameras)

    @app.route('/setup')
    def camera_setup():
        return render_template('camera_setup.html')

    @app.route('/recordings')
    def recordings():
        return render_template('recordings.html')

    @app.route('/settings')
    def settings():
        return render_template('settings.html')

    @app.route('/onvif/<camera_id>')
    def onvif_control(camera_id):
        return render_template('onvif_control.html', camera_id=camera_id)

    # Serve static files
    @app.route('/streams/<path:filename>')
    def serve_stream(filename):
        return send_from_directory(HLS_OUTPUT_DIR, filename)

    @app.route('/snapshots/<filename>')
    def serve_snapshot(filename):
        return send_from_directory(SNAPSHOTS_DIR, filename)

    @app.route('/clips/<filename>')
    def serve_clip(filename):
        return send_from_directory(CLIPS_DIR, filename)

    # Error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized', 'message': 'Invalid or missing authentication token'}), 401

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal Server Error: %s", error)
        return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected error occurred'}), 500

    return app


if __name__ == "__main__":
    app = create_app()

    # Check for FFmpeg
    if not check_ffmpeg():
        logger.warning("FFmpeg not found. Please install FFmpeg for streaming functionality.")

    # Environment check
    if app.config['SECRET_KEY'] == 'dev-secret-key-change-in-production':
        logger.warning("Using default secret key! Set SECRET_KEY environment variable for production.")

    if app.config['API_TOKEN'] == 'dev-api-token-change-in-production':
        logger.warning("Using default API token! Set API_TOKEN environment variable for production.")

    logger.info("Starting Camera Dashboard on http://0.0.0.0:5000")
    logger.info(f"Cloudflare Tunnel: {app.config['CLOUDFLARE_TUNNEL']}")

    app.run(host="0.0.0.0", port=5000, debug=True)