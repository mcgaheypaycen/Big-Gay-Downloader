"""
Conversion queue manager for YouTube Downloader application.
Handles FIFO queue with worker thread for file conversions.
"""

import threading
import queue
import time
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum


class ConversionStatus(Enum):
    """Status of a conversion job."""
    PENDING = "pending"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConversionJob:
    """Represents a file conversion job."""
    input_path: str
    target_format: str  # 'mp4' or 'mp3'
    output_folder: str
    status: ConversionStatus = ConversionStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    title: Optional[str] = None  # Display name for the job
    
    def __hash__(self):
        """Make ConversionJob hashable based on input_path, target_format, and output_folder."""
        return hash((self.input_path, self.target_format, self.output_folder))


class ConversionQueue:
    """
    FIFO queue manager for conversion jobs with worker thread.
    """
    
    def __init__(self, conversion_callback: Callable[[ConversionJob], None], max_size: int = 50):
        """
        Initialize the conversion queue.
        
        Args:
            conversion_callback: Function to call when a job should be converted
            max_size: Maximum number of jobs in the queue
        """
        self._jobs: List[ConversionJob] = []  # List-based queue for proper removal
        self._conversion_callback = conversion_callback
        self._worker_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # Pause event
        self._pause_event.set()  # Start paused by default
        self._current_job: Optional[ConversionJob] = None
        self._lock = threading.Lock()
        self._max_size = max_size
        self._condition = threading.Condition(self._lock)  # For thread synchronization
        
    def start(self):
        """Start the worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._pause_event.clear()  # Clear pause when starting
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
        else:
            # If thread is already running, just resume it
            self.resume()
    
    def stop(self):
        """Stop the worker thread."""
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()  # Wake up worker thread
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
    
    def pause(self):
        """Pause the worker thread (it will stop processing new jobs)."""
        self._pause_event.set()
        print("[DEBUG] Conversion queue paused")
    
    def resume(self):
        """Resume the worker thread (it will start processing jobs again)."""
        self._pause_event.clear()
        with self._condition:
            self._condition.notify_all()  # Wake up worker thread
        print("[DEBUG] Conversion queue resumed")
    
    def is_paused(self) -> bool:
        """Check if the queue is currently paused."""
        return self._pause_event.is_set()
    
    def add_job(self, job: ConversionJob) -> bool:
        """
        Add a job to the queue.
        
        Args:
            job: The conversion job to add
            
        Returns:
            True if job was added successfully, False if queue is full
        """
        with self._lock:
            if len(self._jobs) >= self._max_size:
                return False
            self._jobs.append(job)
            self._condition.notify_all()  # Wake up worker thread
            return True
    
    def is_queue_full(self) -> bool:
        """Check if the queue is full."""
        with self._lock:
            return len(self._jobs) >= self._max_size
    
    def get_queue_capacity(self) -> int:
        """Get the maximum capacity of the queue."""
        return self._max_size
    
    def cancel_job(self, job: ConversionJob) -> bool:
        """
        Cancel a specific job (mark as failed).
        
        Args:
            job: The job to cancel
            
        Returns:
            True if job was cancelled
        """
        with self._lock:
            if self._current_job == job:
                job.status = ConversionStatus.FAILED
                return True
            
            # Mark as failed if in queue
            if job in self._jobs:
                job.status = ConversionStatus.FAILED
                return True
        
        return False
    
    def remove_job(self, job: ConversionJob) -> bool:
        """
        Remove a specific job from the queue completely.
        
        Args:
            job: The job to remove
            
        Returns:
            True if job was removed
        """
        with self._lock:
            # Remove from queue if it's there
            if job in self._jobs:
                self._jobs.remove(job)
                print(f"[DEBUG] Removed conversion job from queue: {job.title}")
                return True
            
            # If it's the current job, mark as failed to stop processing
            if self._current_job == job:
                job.status = ConversionStatus.FAILED
                print(f"[DEBUG] Marked current conversion job as failed to stop processing: {job.title}")
                return True
            
            # If job was popped but not yet set as current, mark as failed to prevent processing
            if job.status == ConversionStatus.PENDING:
                print(f"[DEBUG] Conversion job was popped but not current, marking as failed: {job.title}")
                job.status = ConversionStatus.FAILED
                return True
        
        return False
    
    def get_current_job(self) -> Optional[ConversionJob]:
        """Get the currently converting job."""
        with self._lock:
            return self._current_job
    
    def get_queue_size(self) -> int:
        """Get the number of jobs in the queue."""
        with self._lock:
            return len(self._jobs)
    
    def clear_queue(self):
        """Clear all pending jobs."""
        with self._lock:
            # Mark all jobs as failed
            for job in self._jobs:
                job.status = ConversionStatus.FAILED
            self._jobs.clear()
    
    def _worker_loop(self):
        """Main worker loop that processes jobs."""
        while not self._stop_event.is_set():
            try:
                # Check if we're paused
                if self._pause_event.is_set():
                    with self._condition:
                        self._condition.wait(timeout=0.1)
                    continue
                
                # Get next job
                job = None
                with self._condition:
                    while not self._stop_event.is_set() and not self._pause_event.is_set():
                        # Find next pending job
                        for i, queued_job in enumerate(self._jobs):
                            if queued_job.status == ConversionStatus.PENDING:
                                job = self._jobs.pop(i)
                                break
                        
                        if job is not None:
                            break
                        
                        # No jobs available, wait
                        self._condition.wait(timeout=1)
                
                if job is None:
                    continue
                
                # Set as current job outside the condition block to avoid deadlock
                with self._lock:
                    self._current_job = job
                
                # Double-check that job is still pending before processing
                if job.status != ConversionStatus.PENDING:
                    print(f"[DEBUG] Skipping conversion job {job.title} - status is {job.status.value}")
                    with self._lock:
                        self._current_job = None
                    continue
                
                # Additional check: if job was removed from UI (status changed to FAILED), skip it
                if job.status == ConversionStatus.FAILED:
                    print(f"[DEBUG] Conversion job was marked as failed after popping, skipping: {job.title}")
                    with self._lock:
                        self._current_job = None
                    continue
                
                try:
                    # Update status to converting
                    job.status = ConversionStatus.CONVERTING
                    job.progress = 0.0
                    
                    # Call the conversion callback
                    self._conversion_callback(job)
                    
                    # Mark job as completed if not already marked
                    if job.status == ConversionStatus.CONVERTING:
                        job.status = ConversionStatus.COMPLETED
                        job.progress = 100.0
                        
                except Exception as e:
                    # Only set as failed if not already cancelled/removed
                    if job.status == ConversionStatus.CONVERTING:
                        job.status = ConversionStatus.FAILED
                        job.error_message = str(e)
                
                finally:
                    with self._lock:
                        self._current_job = None
                    
            except Exception as e:
                # Log error and continue
                print(f"Conversion worker thread error: {e}")
                continue
    
    def update_job_progress(self, job: ConversionJob, progress: float):
        """
        Update the progress of a job.
        
        Args:
            job: The job to update
            progress: Progress percentage (0-100)
        """
        if job.status == ConversionStatus.CONVERTING:
            job.progress = max(0.0, min(100.0, progress))
    
    def is_job_processing(self, job: ConversionJob) -> bool:
        """
        Check if a job is currently being processed.
        
        Args:
            job: The job to check
            
        Returns:
            True if the job is currently being processed
        """
        with self._lock:
            return self._current_job == job 