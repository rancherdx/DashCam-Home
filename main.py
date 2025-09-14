from flask import (Flask, jsonify, render_template, send_from_directory,
                   current_app, request, session, redirect, url_for, flash)
import logging
import os
import subprocess
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from backend.camera_manager import CameraManager
from backend.stream_processor import StreamProcessor
from backend.onvif_controller import ONVIFController
from backend.recording_manager import RecordingManager
from backend.settings_manager import SettingsManager
from backend.motion_detector import MotionDetector
from backend.logger_setup import setup_logging, check_ffmpeg
from frontend.api_routes import create_api_routes
from config import SNAPSHOTS_DIR, CLIPS_DIR, THUMBNAILS_DIR, HLS_OUTPUT_DIR

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')

    # Initialize settings manager first
    app.settings_manager = SettingsManager()
    settings = app.settings_manager.get_all_settings()

    # Configuration
    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'API_TOKEN': os.environ.get('API_TOKEN', 'dev-api-token-change-in-production'),
        'CLOUDFLARE_TUNNEL': settings.get('cloudflare', {}).get('enable_https', False),
        'CLOUDFLARE_DOMAIN': settings.get('cloudflare', {}).get('domain', ''),
    })

    # Initialize other components
    app.stream_processor = StreamProcessor(cloudflare_enabled=app.config['CLOUDFLARE_TUNNEL'])
    app.onvif_controller = ONVIFController()
    app.recording_manager = RecordingManager(
        SNAPSHOTS_DIR,
        CLIPS_DIR,
        THUMBNAILS_DIR,
        settings_manager=app.settings_manager
    )
    app.camera_manager = CameraManager(
        stream_processor=app.stream_processor,
        onvif_controller=app.onvif_controller,
        settings_manager=app.settings_manager
    )

    # Wire up circular dependencies
    app.camera_manager.recording_manager = app.recording_manager
    app.recording_manager.camera_manager = app.camera_manager

    # Initialize and start motion detector
    app.motion_detector = MotionDetector(
        camera_manager=app.camera_manager,
        recording_manager=app.recording_manager,
        settings_manager=app.settings_manager
    )

    # Register API routes
    api_blueprint = create_api_routes(
        camera_manager=app.camera_manager,
        stream_processor=app.stream_processor,
        onvif_controller=app.onvif_controller,
        recording_manager=app.recording_manager,
        settings_manager=app.settings_manager
    )
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # --- Authentication and Setup Logic ---

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not app.settings_manager.get_setting('setup_complete'):
                return redirect(url_for('setup'))
            if 'logged_in' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        if app.settings_manager.get_setting('setup_complete'):
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not password or password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('setup.html')

            hashed_password = generate_password_hash(password)
            app.settings_manager.update_settings({
                'admin_password': hashed_password,
                'setup_complete': True
            })
            flash('Admin account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('setup.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if app.settings_manager.get_setting('setup_complete') and 'logged_in' in session:
            return redirect(url_for('dashboard'))
        if not app.settings_manager.get_setting('setup_complete'):
            return redirect(url_for('setup'))

        if request.method == 'POST':
            password = request.form.get('password')
            hashed_password = app.settings_manager.get_setting('admin_password')

            if hashed_password and check_password_hash(hashed_password, password):
                session['logged_in'] = True
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid password.', 'error')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        flash('You have been logged out.', 'success')
        return redirect(url_for('login'))


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
    @login_required
    def dashboard():
        cameras = app.camera_manager.get_all_cameras()
        return render_template('dashboard.html', cameras=cameras)

    @app.route('/camera_setup')
    @login_required
    def camera_setup():
        return render_template('camera_setup.html')

    @app.route('/recordings')
    @login_required
    def recordings():
        return render_template('recordings.html')

    @app.route('/settings')
    @login_required
    def settings():
        return render_template('settings.html')

    @app.route('/onvif/<camera_id>')
    @login_required
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

    # Start motion detection service
    app.motion_detector.start()

    if not check_ffmpeg():
        logger.warning("FFmpeg not found. Please install FFmpeg for streaming functionality.")

    if app.config['SECRET_KEY'] == 'dev-secret-key-change-in-production':
        logger.warning("Using default secret key! Set SECRET_KEY environment variable for production.")

    if app.config['API_TOKEN'] == 'dev-api-token-change-in-production':
        logger.warning("Using default API token! Set API_TOKEN environment variable for production.")

    logger.info("Starting Camera Dashboard on http://0.0.0.0:5000")
    logger.info(f"Cloudflare Tunnel: {app.config['CLOUDFLARE_TUNNEL']}")

    app.run(host="0.0.0.0", port=5000, debug=True)