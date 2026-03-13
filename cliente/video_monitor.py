"""
Video Monitor for Scheduled Playback

This module monitors the received_files directory for video files,
parses flags from filenames, and handles immediate or scheduled playback.
"""

import os
import re
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    BackgroundScheduler = None
    CronTrigger = None

from config import RECEIVE_DIR, MONITOR_INTERVAL, VIDEO_EXTENSIONS, VIDEO_PLAYER


logger = logging.getLogger(__name__)


class VideoMonitor:
    """
    Monitors a directory for video files and handles playback based on flags.
    
    Supported flags:
    - No flag: video.mp4 -> Play immediately with audio
    - SILENT: video.SILENT.mp4 -> Play immediately without audio
    - SCHED: video.SCHED_14:30_1,3,5.mp4 -> Schedule for Mon, Wed, Fri at 14:30
    """
    
    def __init__(self, watch_directory: str = RECEIVE_DIR):
        """
        Initialize the video monitor.
        
        Args:
            watch_directory: Directory to monitor for video files
        """
        self.watch_directory = Path(watch_directory)
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Initialize scheduler for scheduled playback
        self.scheduler = None
        if BackgroundScheduler and CronTrigger:
            try:
                self.scheduler = BackgroundScheduler()
                self.scheduler.start()
                logger.info("APScheduler initialized for video scheduling")
            except Exception as e:
                logger.error(f"Failed to initialize scheduler: {e}")
        else:
            logger.warning("APScheduler not available, scheduled playback disabled")
        
        # Ensure watch directory exists
        self.watch_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"VideoMonitor initialized, watching: {self.watch_directory}")
    
    def start_monitoring(self) -> None:
        """Start monitoring the directory in a separate thread."""
        if self.running:
            logger.warning("VideoMonitor is already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("VideoMonitor started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring the directory and shutdown scheduler."""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        if self.scheduler:
            self.scheduler.shutdown()
        
        logger.info("VideoMonitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop that checks for video files."""
        logger.info("VideoMonitor loop started")
        
        while self.running:
            try:
                # Scan for video files
                video_files = []
                for ext in VIDEO_EXTENSIONS:
                    video_files.extend(self.watch_directory.glob(f"*{ext}"))
                
                for video_file in video_files:
                    try:
                        self.process_video_file(str(video_file))
                    except Exception as e:
                        logger.error(f"Error processing {video_file}: {e}", exc_info=True)
                
                # Sleep for the configured interval
                time.sleep(MONITOR_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(MONITOR_INTERVAL)
    
    def process_video_file(self, filepath: str) -> None:
        """
        Process a video file based on its flag.
        
        Args:
            filepath: Path to the video file
        """
        logger.info(f"Processing video file: {filepath}")
        
        try:
            # Parse flag from filename
            flag_info = self.parse_video_flag(filepath)
            
            flag_type = flag_info['type']
            logger.info(f"Video flag type: {flag_type}")
            
            if flag_type == 'immediate':
                # Play immediately with audio
                self.play_video(filepath, silent=False)
                # Delete after playback
                os.remove(filepath)
                logger.info(f"Deleted video file after playback: {filepath}")
                
            elif flag_type == 'silent':
                # Play immediately without audio
                self.play_video(filepath, silent=True)
                # Delete after playback
                os.remove(filepath)
                logger.info(f"Deleted video file after playback: {filepath}")
                
            elif flag_type == 'scheduled':
                # Schedule playback
                time_str = flag_info['time']
                days = flag_info['days']
                self.schedule_video(filepath, time_str, days)
                logger.info(f"Scheduled video for {time_str} on days {days}")
            
            else:
                logger.error(f"Unknown flag type: {flag_type}")
                
        except Exception as e:
            logger.error(f"Failed to process video file {filepath}: {e}", exc_info=True)
    
    def parse_video_flag(self, filename: str) -> Dict:
        """
        Parse flag from video filename.
        
        Args:
            filename: Full path to video file
        
        Returns:
            Dict with keys: 'type', 'time' (optional), 'days' (optional)
            type can be: 'immediate', 'silent', 'scheduled'
        
        Examples:
            video.mp4 -> {'type': 'immediate'}
            video.SILENT.mp4 -> {'type': 'silent'}
            video.SCHED_14:30_1,3,5.mp4 -> {'type': 'scheduled', 'time': '14:30', 'days': [1,3,5]}
        """
        basename = os.path.basename(filename)
        
        # Check for SCHED flag
        sched_pattern = r'\.SCHED_(\d{1,2}:\d{2})_([\d,]+)\.'
        sched_match = re.search(sched_pattern, basename)
        
        if sched_match:
            time_str = sched_match.group(1)
            days_str = sched_match.group(2)
            
            # Parse days
            try:
                days = [int(d.strip()) for d in days_str.split(',')]
                # Validate days (1-7)
                if not all(1 <= d <= 7 for d in days):
                    raise ValueError(f"Invalid day values: {days}")
            except ValueError as e:
                logger.error(f"Invalid days format in {basename}: {e}")
                raise
            
            # Validate time format
            try:
                hour, minute = map(int, time_str.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"Invalid time: {time_str}")
            except ValueError as e:
                logger.error(f"Invalid time format in {basename}: {e}")
                raise
            
            return {
                'type': 'scheduled',
                'time': time_str,
                'days': days
            }
        
        # Check for SILENT flag
        if '.SILENT.' in basename:
            return {'type': 'silent'}
        
        # Default: immediate playback
        return {'type': 'immediate'}
    
    def play_video(self, filepath: str, silent: bool = False) -> None:
        """
        Play video immediately using configured video player.
        
        Args:
            filepath: Path to video file
            silent: If True, play without audio
        """
        logger.info(f"Playing video: {filepath} (silent={silent})")
        
        try:
            # Build command based on video player
            if VIDEO_PLAYER == "vlc":
                cmd = ["vlc", "--play-and-exit", "--fullscreen"]
                if silent:
                    cmd.append("--no-audio")
                cmd.append(filepath)
            elif VIDEO_PLAYER == "mpv":
                cmd = ["mpv", "--fullscreen"]
                if silent:
                    cmd.append("--no-audio")
                cmd.append(filepath)
            else:
                logger.error(f"Unsupported video player: {VIDEO_PLAYER}")
                return
            
            # Execute video player
            logger.debug(f"Executing command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3600  # 1 hour max
            )
            
            if result.returncode == 0:
                logger.info(f"Video playback completed: {filepath}")
            else:
                logger.error(
                    f"Video playback failed with code {result.returncode}: "
                    f"{result.stderr.decode('utf-8', errors='ignore')}"
                )
                
        except subprocess.TimeoutExpired:
            logger.error(f"Video playback timed out: {filepath}")
        except FileNotFoundError:
            logger.error(f"Video player '{VIDEO_PLAYER}' not found")
        except Exception as e:
            logger.error(f"Video playback error: {e}", exc_info=True)
    
    def schedule_video(self, filepath: str, time_str: str, days: List[int]) -> None:
        """
        Schedule video playback for specific time and days.
        
        Args:
            filepath: Path to video file
            time_str: Time in HH:MM format (24-hour)
            days: List of day numbers (1=Monday, 7=Sunday)
        """
        if not self.scheduler:
            logger.error("Scheduler not available, cannot schedule video")
            return
        
        logger.info(f"Scheduling video: {filepath} at {time_str} on days {days}")
        
        try:
            # Parse time
            hour, minute = map(int, time_str.split(':'))
            
            # Convert days to cron format (0=Monday in APScheduler)
            # Our format: 1=Monday, 7=Sunday
            # APScheduler: 0=Monday, 6=Sunday
            cron_days = [str(d - 1) for d in days]
            day_of_week = ','.join(cron_days)
            
            # Create cron trigger
            trigger = CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute
            )
            
            # Schedule the job
            job_id = f"video_{os.path.basename(filepath)}_{time.time()}"
            self.scheduler.add_job(
                func=self._scheduled_playback,
                trigger=trigger,
                args=[filepath],
                id=job_id,
                replace_existing=False
            )
            
            logger.info(
                f"Video scheduled successfully: {filepath} "
                f"at {time_str} on days {days} (job_id: {job_id})"
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule video: {e}", exc_info=True)
    
    def _scheduled_playback(self, filepath: str) -> None:
        """
        Callback for scheduled video playback.
        
        Args:
            filepath: Path to video file
        """
        logger.info(f"Executing scheduled playback: {filepath}")
        
        try:
            # Check if file still exists
            if not os.path.exists(filepath):
                logger.warning(f"Scheduled video file not found: {filepath}")
                return
            
            # Play video with audio (scheduled videos always have audio)
            self.play_video(filepath, silent=False)
            
            # Note: Scheduled videos are NOT deleted after playback
            # They remain for future scheduled playbacks
            
        except Exception as e:
            logger.error(f"Scheduled playback failed: {e}", exc_info=True)


def main():
    """Main function for testing the video monitor."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = VideoMonitor()
    monitor.start_monitoring()
    
    try:
        logger.info("VideoMonitor running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping VideoMonitor...")
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()
