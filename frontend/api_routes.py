from flask import Blueprint, request, jsonify, send_file, abort, current_app
import logging
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
import secrets

logger = logging.getLogger(__name__)

def create_api_routes(camera_manager, stream_processor, onvif_controller, recording_manager, settings_manager):
    api_bp = Blueprint('api', __name__)
    access_logger = logging.getLogger('api.access')
    
    # Store reference to components
    api_bp.camera_manager = camera_manager
    api_bp.stream_processor = stream_processor
    api_bp.onvif_controller = onvif_controller
    api_bp.recording_manager = recording_manager
    api_bp.settings_manager = settings_manager

    def token_required(f):
        """Decorator to require authentication token for API endpoints"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip authentication in development if disabled
            if current_app.config.get('ENV') == 'development' and current_app.config.get('DISABLE_AUTH'):
                return f(*args, **kwargs)

            token = request.headers.get('X-Auth-Token') or request.args.get('token')
            if not token or token != current_app.config.get('API_TOKEN'):
                access_logger.warning(f"Unauthorized access to {request.path} from {request.remote_addr}")
                abort(401)

            access_logger.info(f"Authorized access to {request.path} from {request.remote_addr}")
            return f(*args, **kwargs)
        return decorated_function

    def stream_token_required(f):
        """Decorator for stream token authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            camera_id = kwargs.get('camera_id')
            token = request.args.get('token')

            if not token or not stream_processor.verify_stream_token(camera_id, token):
                access_logger.warning(f"Invalid stream token for camera {camera_id} from {request.remote_addr}")
                abort(401)
            return f(*args, **kwargs)
        return decorated_function

    @api_bp.route('/auth/login', methods=['POST'])
    def login():
        """Login endpoint to get API token"""
        data = request.get_json(silent=True) # Use silent=True to avoid errors on empty body
        # In a real application, you'd validate credentials here
        # For simplicity, we're using a single API token
        return jsonify({
            'token': current_app.config.get('API_TOKEN'),
            'expires': (datetime.now() + timedelta(hours=24)).isoformat()
        })
    
    @api_bp.route('/stream/auth/<camera_id>')
    @token_required
    def get_stream_auth(camera_id):
        """Get a temporary token to access a stream"""
        token = stream_processor.generate_stream_token(camera_id)
        expiry = datetime.now() + current_app.config.get('TOKEN_EXPIRY', timedelta(hours=1))
        return jsonify({
            'token': token, 
            'camera_id': camera_id,
            'expires': expiry.isoformat()
        })
    
    @api_bp.route('/streams/<camera_id>/<path:filename>')
    @stream_token_required
    def serve_stream_file(camera_id, filename):
        """Serve HLS stream files with token verification"""
        try:
            stream_path = Path(current_app.config['HLS_OUTPUT_DIR']) / camera_id
            if not stream_path.exists():
                abort(404)
            return send_from_directory(stream_path, filename)
        except Exception as e:
            logger.error(f"Error serving stream file: {e}")
            abort(404)
    
    # Camera management endpoints
    @api_bp.route('/cameras', methods=['GET'])
    @token_required
    def get_cameras():
        return jsonify(camera_manager.get_all_cameras())
    
    @api_bp.route('/cameras', methods=['POST'])
    @token_required
    def add_camera():
        data = request.json
        camera_id = camera_manager.add_camera(data)
        return jsonify({'camera_id': camera_id, 'message': 'Camera added successfully'})
    
    @api_bp.route('/cameras/<camera_id>', methods=['GET'])
    @token_required
    def get_camera(camera_id):
        camera = camera_manager.get_camera_status(camera_id)
        if not camera:
            abort(404, description="Camera not found")
        return jsonify(camera)

    @api_bp.route('/cameras/<camera_id>', methods=['PUT'])
    @token_required
    def update_camera(camera_id):
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        success = camera_manager.update_camera(camera_id, data)
        if not success:
            abort(404, description="Camera not found or update failed")
        return jsonify({'success': success, 'message': 'Camera updated successfully'})

    @api_bp.route('/cameras/<camera_id>', methods=['DELETE'])
    @token_required
    def remove_camera(camera_id):
        success = camera_manager.remove_camera(camera_id)
        return jsonify({'success': success, 'message': 'Camera removed' if success else 'Camera not found'})
    
    # Stream control endpoints
    @api_bp.route('/stream/start/<camera_id>', methods=['POST'])
    @token_required
    def start_stream(camera_id):
        data = request.json or {}
        profile = data.get('profile', 'main')
        success = camera_manager.start_stream(camera_id, profile)
        return jsonify({'success': success, 'message': 'Stream started' if success else 'Stream start failed'})
    
    @api_bp.route('/stream/stop/<camera_id>', methods=['POST'])
    @token_required
    def stop_stream(camera_id):
        success = camera_manager.stop_stream(camera_id)
        return jsonify({'success': success, 'message': 'Stream stopped' if success else 'Stream stop failed'})
    
    @api_bp.route('/stream/restart/<camera_id>', methods=['POST'])
    @token_required
    def restart_stream(camera_id):
        camera_manager.stop_stream(camera_id)
        success = camera_manager.start_stream(camera_id)
        return jsonify({'success': success, 'message': 'Stream restarted' if success else 'Stream restart failed'})
    
    # ONVIF endpoints
    @api_bp.route('/onvif/connect/<camera_id>', methods=['POST'])
    @token_required
    def connect_onvif(camera_id):
        camera = camera_manager.get_camera_status(camera_id)
        if not camera:
            abort(404)
        
        success = onvif_controller.connect_camera(
            camera_id, 
            camera['ip'], 
            camera.get('onvif_port', 80),
            camera['username'], 
            camera['password']
        )
        return jsonify({'success': success})
    
    @api_bp.route('/onvif/profiles/<camera_id>', methods=['GET'])
    @token_required
    def get_onvif_profiles(camera_id):
        profiles = onvif_controller.get_profiles(camera_id)
        return jsonify(profiles)
    
    @api_bp.route('/onvif/ptz/<camera_id>', methods=['POST'])
    @token_required
    def ptz_control(camera_id):
        data = request.json
        command = data.get('command')
        # Implement PTZ control logic here
        return jsonify({'success': True, 'command': command})
    
    @api_bp.route('/onvif/motion_rules/<camera_id>/<profile_token>', methods=['GET'])
    @token_required
    def get_motion_rules(camera_id, profile_token):
        rules = onvif_controller.get_motion_detection_rules(camera_id, profile_token)
        return jsonify(rules)

    # Recording endpoints
    @api_bp.route('/recordings', methods=['GET'])
    @token_required
    def get_recordings():
        camera_id = request.args.get('camera_id')
        hours = int(request.args.get('hours', 7))
        recordings = recording_manager.get_recordings(camera_id, hours)
        return jsonify(recordings)
    
    @api_bp.route('/snapshot/<camera_id>', methods=['POST'])
    @token_required
    def take_snapshot(camera_id):
        # Implementation for taking snapshot
        filename = recording_manager.take_snapshot(camera_id, b'')  # Empty bytes for demo
        return jsonify({'success': bool(filename), 'filename': filename})
    
    @api_bp.route('/recording/start/<camera_id>', methods=['POST'])
    @token_required
    def start_recording(camera_id):
        filename = recording_manager.start_recording(camera_id)
        return jsonify({'success': bool(filename), 'filename': filename})
    
    @api_bp.route('/recording/stop/<camera_id>', methods=['POST'])
    @token_required
    def stop_recording(camera_id):
        # Implementation to stop recording
        return jsonify({'success': True, 'message': 'Recording stopped'})
    
    # System endpoints
    @api_bp.route('/system/status', methods=['GET'])
    @token_required
    def system_status():
        return jsonify({
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'cameras_count': len(camera_manager.get_all_cameras()),
            'active_streams': len([c for c in camera_manager.get_all_cameras() if c.get('stream_active')])
        })
    
    @api_bp.route('/system/stats', methods=['GET'])
    @token_required
    def system_stats():
        """Returns system statistics like CPU, memory, and network usage."""
        import psutil

        # Get network stats
        net_io = psutil.net_io_counters()

        stats = {
            'cpu_usage': psutil.cpu_percent(interval=0.1),
            'memory': {
                'total': psutil.virtual_memory().total,
                'used': psutil.virtual_memory().used,
                'percent': psutil.virtual_memory().percent
            },
            'network': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv
            }
        }
        return jsonify(stats)

    @api_bp.route('/system/restart', methods=['POST'])
    @token_required
    def system_restart():
        # This is complex to implement safely. For now, we'll just log it.
        logger.warning("System restart requested via API. This feature is not fully implemented.")
        return jsonify({'success': True, 'message': 'Restart initiated (logging only)'})

    # Settings Endpoints
    @api_bp.route('/settings', methods=['GET'])
    @token_required
    def get_settings():
        return jsonify(settings_manager.get_all_settings())

    @api_bp.route('/settings', methods=['POST'])
    @token_required
    def update_settings():
        new_settings = request.json
        if not new_settings:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        # Add validation logic here in a real application
        settings_manager.update_settings(new_settings)
        return jsonify({'success': True, 'message': 'Settings updated successfully'})

    @api_bp.route('/settings/export', methods=['GET'])
    @token_required
    def export_settings():
        """Exports the current settings as a JSON file."""
        settings = settings_manager.get_all_settings()
        return jsonify(settings), 200, {
            'Content-Disposition': 'attachment; filename=camera_dashboard_config.json'
        }

    @api_bp.route('/system/logs', methods=['GET'])
    @token_required
    def list_logs():
        """Lists available log files."""
        from config import LOGS_DIR
        import os
        try:
            logs = [f for f in os.listdir(LOGS_DIR) if f.endswith('.log')]
            return jsonify(logs)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @api_bp.route('/system/logs/<filename>', methods=['GET'])
    @token_required
    def get_log_file(filename):
        """Returns the content of a specific log file."""
        from config import LOGS_DIR
        from flask import send_from_directory
        # Basic security check
        if '..' in filename or filename.startswith('/'):
            abort(400, "Invalid filename.")

        return send_from_directory(LOGS_DIR, filename, as_attachment=True)

    return api_bp