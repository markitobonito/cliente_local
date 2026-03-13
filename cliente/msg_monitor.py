"""
Message Monitor for TTS Alerts

This module monitors the received_files directory for .msg files,
parses them, plays TTS alerts, and displays desktop notifications.
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    from plyer import notification
except ImportError:
    notification = None

from config import RECEIVE_DIR, MONITOR_INTERVAL, MAX_ALERT_REPETITIONS, TTS_ENGINE


logger = logging.getLogger(__name__)


class MessageMonitor:
    """
    Monitors a directory for .msg files and processes them as TTS alerts.
    
    Message format: repetitions|message
    Example: 3|Meeting in 5 minutes
    """
    
    def __init__(self, watch_directory: str = RECEIVE_DIR):
        """
        Initialize the message monitor.
        
        Args:
            watch_directory: Directory to monitor for .msg files
        """
        self.watch_directory = Path(watch_directory)
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Initialize TTS engine
        self.tts_engine = None
        if TTS_ENGINE == "pyttsx3" and pyttsx3:
            try:
                self.tts_engine = pyttsx3.init()
                logger.info("TTS engine initialized: pyttsx3")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3: {e}")
        
        # Ensure watch directory exists
        self.watch_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"MessageMonitor initialized, watching: {self.watch_directory}")
    
    def start_monitoring(self) -> None:
        """Start monitoring the directory in a separate thread."""
        if self.running:
            logger.warning("MessageMonitor is already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("MessageMonitor started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring the directory."""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("MessageMonitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop that checks for .msg files."""
        logger.info("MessageMonitor loop started")
        
        while self.running:
            try:
                # Scan for .msg files
                msg_files = list(self.watch_directory.glob("*.msg"))
                
                for msg_file in msg_files:
                    try:
                        self.process_msg_file(str(msg_file))
                    except Exception as e:
                        logger.error(f"Error processing {msg_file}: {e}", exc_info=True)
                
                # Sleep for the configured interval
                time.sleep(MONITOR_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(MONITOR_INTERVAL)
    
    def process_msg_file(self, filepath: str) -> None:
        """
        Process a .msg file: parse, play TTS, show notification, delete.
        
        Args:
            filepath: Path to the .msg file
        
        Format: repetitions|message
        Example: 3|Meeting in 5 minutes
        """
        logger.info(f"Processing message file: {filepath}")
        
        try:
            # Read file content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Parse content
            repetitions, message = self.parse_msg_content(content)
            
            logger.info(f"Parsed alert: repetitions={repetitions}, message='{message}'")
            
            # Display notification
            self._show_notification(message, repetitions)
            
            # Play TTS
            self.play_tts(message, repetitions)
            
            # Delete the file after processing
            os.remove(filepath)
            logger.info(f"Deleted processed message file: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to process message file {filepath}: {e}", exc_info=True)
            # Try to delete the file even if processing failed to avoid reprocessing
            try:
                os.remove(filepath)
                logger.info(f"Deleted failed message file: {filepath}")
            except Exception as del_error:
                logger.error(f"Failed to delete message file {filepath}: {del_error}")
    
    def parse_msg_content(self, content: str) -> Tuple[int, str]:
        """
        Parse message content in format: repetitions|message
        
        Args:
            content: Raw content from .msg file
        
        Returns:
            Tuple of (repetitions, message)
        
        Raises:
            ValueError: If content format is invalid
        """
        if '|' not in content:
            raise ValueError("Message content must contain '|' separator")
        
        parts = content.split('|', 1)
        if len(parts) != 2:
            raise ValueError("Message content must have exactly one '|' separator")
        
        repetitions_str, message = parts
        
        # Parse repetitions
        try:
            repetitions = int(repetitions_str.strip())
        except ValueError:
            raise ValueError(f"Invalid repetitions value: '{repetitions_str}'")
        
        # Validate repetitions
        if repetitions < 1:
            raise ValueError(f"Repetitions must be at least 1, got: {repetitions}")
        
        if repetitions > MAX_ALERT_REPETITIONS:
            logger.warning(
                f"Repetitions {repetitions} exceeds max {MAX_ALERT_REPETITIONS}, "
                f"capping to {MAX_ALERT_REPETITIONS}"
            )
            repetitions = MAX_ALERT_REPETITIONS
        
        # Validate message
        message = message.strip()
        if not message:
            raise ValueError("Message text cannot be empty")
        
        return repetitions, message
    
    def play_tts(self, message: str, repetitions: int) -> None:
        """
        Play message using Text-to-Speech N times.
        
        Args:
            message: Text to speak
            repetitions: Number of times to repeat the message
        """
        if not self.tts_engine:
            logger.warning("TTS engine not available, skipping TTS playback")
            return
        
        logger.info(f"Playing TTS: '{message}' x{repetitions}")
        
        try:
            for i in range(repetitions):
                logger.debug(f"TTS repetition {i+1}/{repetitions}")
                self.tts_engine.say(message)
                self.tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS playback failed: {e}", exc_info=True)
    
    def _show_notification(self, message: str, repetitions: int) -> None:
        """
        Display desktop notification.
        
        Args:
            message: Notification message
            repetitions: Number of repetitions (shown in title)
        """
        if not notification:
            logger.warning("Notification library not available, skipping notification")
            return
        
        try:
            notification.notify(
                title=f"Alert (x{repetitions})",
                message=message,
                app_name="LAN File Transfer",
                timeout=10  # seconds
            )
            logger.info(f"Displayed notification: '{message}'")
        except Exception as e:
            logger.error(f"Failed to display notification: {e}", exc_info=True)


def main():
    """Main function for testing the message monitor."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = MessageMonitor()
    monitor.start_monitoring()
    
    try:
        logger.info("MessageMonitor running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping MessageMonitor...")
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()
