"""
Flask Web Application for Client

This module implements the Flask web interface for file uploads, alerts, and videos.
Users can access the interface at http://localhost:1492

Requirements: 5.1, 5.2
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename

from .quic_sender import QUICSender
from .config import FLASK_PORT, RECEIVE_DIR, MAX_FILE_SIZE, MAX_ALERT_REPETITIONS


logger = logging.getLogger(__name__)


class FlaskWebApp:
    """
    Flask web application for client interface.
    
    Provides web interface for:
    - File uploads
    - Alert/notification sending with TTS
    - Video uploads with scheduling flags
    
    Attributes:
        app: Flask application instance
        quic_sender: QUICSender instance for file transmission
        upload_folder: Temporary folder for uploaded files
    """
    
    def __init__(self, quic_sender: QUICSender):
        """
        Initialize the Flask application.
        
        Args:
            quic_sender: QUICSender instance for file transmission
        """
        self.app = Flask(__name__)
        self.quic_sender = quic_sender
        self.upload_folder = Path("./uploads")
        self.upload_folder.mkdir(exist_ok=True)
        
        self.app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
        self.app.config['UPLOAD_FOLDER'] = str(self.upload_folder)
        
        self.setup_routes()
        logger.info("Flask web application initialized")
        
    def setup_routes(self) -> None:
        """Configure all Flask routes."""
        
        @self.app.route('/')
        def index():
            """
            Render the main page (templates/index.html).
            
            Returns:
                Rendered HTML template
            """
            return render_template('index.html')
            
        @self.app.route('/api/upload', methods=['POST'])
        def upload_file():
            """
            Handle file upload from web interface.
            
            Receives file via multipart/form-data, saves temporarily,
            and sends via QUIC to bridge.
            
            Returns:
                JSON response: {'success': bool, 'message': str}
            """
            try:
                # Check if file is present in request
                if 'file' not in request.files:
                    logger.warning("Upload request missing file")
                    return jsonify({'success': False, 'message': 'No file provided'}), 400
                    
                file = request.files['file']
                
                # Check if filename is empty
                if file.filename == '':
                    logger.warning("Upload request with empty filename")
                    return jsonify({'success': False, 'message': 'No file selected'}), 400
                    
                # Secure the filename and save temporarily
                filename = secure_filename(file.filename)
                filepath = self.upload_folder / filename
                
                logger.info(f"Receiving file upload: {filename}")
                file.save(str(filepath))
                
                # Check file size
                file_size = filepath.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    filepath.unlink()
                    logger.error(f"File too large: {file_size} bytes")
                    return jsonify({
                        'success': False,
                        'message': f'File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)'
                    }), 400
                
                # Send file via QUIC
                logger.info(f"Sending file via QUIC: {filename}")
                success = self.quic_sender.send_file_sync(str(filepath))
                
                # Clean up temporary file
                try:
                    filepath.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
                
                if success:
                    logger.info(f"File uploaded and sent successfully: {filename}")
                    return jsonify({
                        'success': True,
                        'message': f'File {filename} sent successfully'
                    }), 200
                else:
                    logger.error(f"Failed to send file via QUIC: {filename}")
                    return jsonify({
                        'success': False,
                        'message': 'Failed to send file to bridge'
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error handling file upload: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Upload error: {str(e)}'
                }), 500
                
        @self.app.route('/send-notification', methods=['POST'])
        def send_notification():
            """
            Send alert/notification with TTS.
            
            Creates a .msg file with format: repetitions|message
            and sends it via QUIC to bridge for distribution.
            
            Expected JSON body:
                {
                    "repetitions": int (1-10),
                    "message": str (non-empty)
                }
            
            Returns:
                JSON response: {'success': bool, 'message': str}
            """
            try:
                data = request.get_json()
                
                if not data:
                    logger.warning("Notification request missing JSON body")
                    return jsonify({'success': False, 'message': 'No data provided'}), 400
                    
                # Validate repetitions
                repetitions = data.get('repetitions')
                if repetitions is None:
                    return jsonify({'success': False, 'message': 'Missing repetitions field'}), 400
                    
                try:
                    repetitions = int(repetitions)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Repetitions must be an integer'}), 400
                    
                if repetitions < 1 or repetitions > MAX_ALERT_REPETITIONS:
                    return jsonify({
                        'success': False,
                        'message': f'Repetitions must be between 1 and {MAX_ALERT_REPETITIONS}'
                    }), 400
                
                # Validate message
                message = data.get('message')
                if not message or not isinstance(message, str) or not message.strip():
                    return jsonify({'success': False, 'message': 'Message must be a non-empty string'}), 400
                    
                message = message.strip()
                
                # Create .msg file with format: repetitions|message
                msg_filename = f"alert_{int(asyncio.get_event_loop().time())}.msg"
                msg_filepath = self.upload_folder / msg_filename
                
                msg_content = f"{repetitions}|{message}"
                
                logger.info(f"Creating alert message: {msg_filename} with content: {msg_content}")
                
                with open(msg_filepath, 'w', encoding='utf-8') as f:
                    f.write(msg_content)
                
                # Send .msg file via QUIC
                logger.info(f"Sending alert via QUIC: {msg_filename}")
                success = self.quic_sender.send_file_sync(str(msg_filepath))
                
                # Clean up temporary file
                try:
                    msg_filepath.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary .msg file: {e}")
                
                if success:
                    logger.info(f"Alert sent successfully: {msg_content}")
                    return jsonify({
                        'success': True,
                        'message': 'Alert sent successfully'
                    }), 200
                else:
                    logger.error(f"Failed to send alert via QUIC: {msg_filename}")
                    return jsonify({
                        'success': False,
                        'message': 'Failed to send alert to bridge'
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error handling notification: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Notification error: {str(e)}'
                }), 500
                
        @self.app.route('/videos', methods=['POST'])
        def upload_video():
            """
            Upload video with optional flag.
            
            Handles video uploads with flags for playback control:
            - No flag: Immediate playback with audio
            - .SILENT: Immediate playback without audio
            - .SCHED_HH:MM_days: Scheduled playback
            
            Expected form data:
                - file: video file
                - flag: optional flag type ('none', 'silent', or 'scheduled')
                - schedule_time: HH:MM format (required if flag='scheduled')
                - schedule_days: comma-separated days 1-7 (required if flag='scheduled')
            
            Returns:
                JSON response: {'success': bool, 'message': str}
            """
            try:
                # Check if file is present
                if 'file' not in request.files:
                    logger.warning("Video upload request missing file")
                    return jsonify({'success': False, 'message': 'No file provided'}), 400
                    
                file = request.files['file']
                
                if file.filename == '':
                    logger.warning("Video upload request with empty filename")
                    return jsonify({'success': False, 'message': 'No file selected'}), 400
                    
                # Get flag type
                flag_type = request.form.get('flag', 'none')
                
                # Secure the filename
                original_filename = secure_filename(file.filename)
                base_name = Path(original_filename).stem
                extension = Path(original_filename).suffix
                
                # Build filename with flag
                if flag_type == 'silent':
                    filename = f"{base_name}.SILENT{extension}"
                elif flag_type == 'scheduled':
                    # Validate schedule parameters
                    schedule_time = request.form.get('schedule_time')
                    schedule_days = request.form.get('schedule_days')
                    
                    if not schedule_time or not schedule_days:
                        return jsonify({
                            'success': False,
                            'message': 'Schedule time and days required for scheduled videos'
                        }), 400
                    
                    # Validate time format (HH:MM)
                    try:
                        time_parts = schedule_time.split(':')
                        if len(time_parts) != 2:
                            raise ValueError("Invalid time format")
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                            raise ValueError("Invalid time values")
                    except (ValueError, IndexError):
                        return jsonify({
                            'success': False,
                            'message': 'Invalid time format (use HH:MM)'
                        }), 400
                    
                    # Validate days (comma-separated 1-7)
                    try:
                        days_list = [int(d.strip()) for d in schedule_days.split(',')]
                        if not all(1 <= d <= 7 for d in days_list):
                            raise ValueError("Days must be between 1 and 7")
                        days_str = ','.join(map(str, days_list))
                    except (ValueError, AttributeError):
                        return jsonify({
                            'success': False,
                            'message': 'Invalid days format (use comma-separated 1-7)'
                        }), 400
                    
                    filename = f"{base_name}.SCHED_{schedule_time}_{days_str}{extension}"
                else:
                    # No flag - immediate playback
                    filename = original_filename
                
                # Save file temporarily
                filepath = self.upload_folder / filename
                
                logger.info(f"Receiving video upload: {filename}")
                file.save(str(filepath))
                
                # Check file size
                file_size = filepath.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    filepath.unlink()
                    logger.error(f"Video too large: {file_size} bytes")
                    return jsonify({
                        'success': False,
                        'message': f'Video too large (max {MAX_FILE_SIZE // (1024*1024)}MB)'
                    }), 400
                
                # Send video via QUIC
                logger.info(f"Sending video via QUIC: {filename}")
                success = self.quic_sender.send_file_sync(str(filepath))
                
                # Clean up temporary file
                try:
                    filepath.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary video file: {e}")
                
                if success:
                    logger.info(f"Video uploaded and sent successfully: {filename}")
                    return jsonify({
                        'success': True,
                        'message': f'Video {filename} sent successfully'
                    }), 200
                else:
                    logger.error(f"Failed to send video via QUIC: {filename}")
                    return jsonify({
                        'success': False,
                        'message': 'Failed to send video to bridge'
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error handling video upload: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Video upload error: {str(e)}'
                }), 500
        
    def run(self, host: str = '0.0.0.0', port: int = FLASK_PORT, debug: bool = False) -> None:
        """
        Start the Flask server.
        
        Args:
            host: Host address to bind to (default: 0.0.0.0)
            port: Port number to listen on (default: 1492 from config)
            debug: Enable debug mode (default: False)
        """
        logger.info(f"Starting Flask web server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)


def create_app(quic_sender: QUICSender) -> Flask:
    """
    Factory function to create Flask app instance.
    
    Args:
        quic_sender: QUICSender instance for file transmission
        
    Returns:
        Flask application instance
    """
    web_app = FlaskWebApp(quic_sender)
    return web_app.app
