"""
Queue manager for YouTube Downloader application.
Handles FIFO queue with worker thread for downloads.
"""

import threading
import queue
import time
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(Enum):
    """Status of a download job."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DownloadJob:
    """Represents a download job."""
    url: str
    format: str  # 'mp4' or 'mp3'
    output_folder: str
    mode: str = "youtube"  # 'youtube' or 'xvideos'
    compatibility_mode: bool = False
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    title: Optional[str] = None
    custom_title: Optional[str] = None  # Track if user manually renamed
    eta: Optional[str] = None
    speed: Optional[str] = None
    progress_widgets: Optional[dict] = None
    
    def __hash__(self):
        """Make DownloadJob hashable based on url, format, and output_folder."""
        return hash((self.url, self.format, self.output_folder))


class DownloadQueue:
    """
    FIFO queue manager for download jobs with worker thread.
    """
    
    def __init__(self, download_callback: Callable[[DownloadJob], None], max_size: int = 100):
        """
        Initialize the download queue.
        
        Args:
            download_callback: Function to call when a job should be downloaded
            max_size: Maximum number of jobs in the queue
        """
        self._jobs: List[DownloadJob] = []  # List-based queue for proper removal
        self._download_callback = download_callback
        self._worker_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # New: pause event
        self._pause_event.set()  # Start paused by default
        self._current_job: Optional[DownloadJob] = None
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
        print("[DEBUG] Download queue paused")
    
    def resume(self):
        """Resume the worker thread (it will start processing jobs again)."""
        self._pause_event.clear()
        with self._condition:
            self._condition.notify_all()  # Wake up worker thread
        print("[DEBUG] Download queue resumed")
    
    def is_paused(self) -> bool:
        """Check if the queue is currently paused."""
        return self._pause_event.is_set()
    
    def add_job(self, job: DownloadJob) -> bool:
        """
        Add a job to the queue.
        
        Args:
            job: The download job to add
            
        Returns:
            True if job was added successfully, False if queue is full
        """
        print(f"[DEBUG] Queue: add_job called with url={job.url}, format={job.format}")
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
    
    def cancel_job(self, job: DownloadJob) -> bool:
        """
        Cancel a specific job (mark as failed).
        
        Args:
            job: The job to cancel
            
        Returns:
            True if job was cancelled
        """
        with self._lock:
            if self._current_job == job:
                job.status = JobStatus.FAILED
                return True
            
            # Mark as failed if in queue
            if job in self._jobs:
                job.status = JobStatus.FAILED
                return True
        
        return False
    
    def remove_job(self, job: DownloadJob) -> bool:
        """
        Remove a specific job from the queue completely.
        
        Args:
            job: The job to remove
            
        Returns:
            True if job was removed
        """
        print(f"[DEBUG] remove_job called for: {job.url} (status: {job.status})")
        
        with self._lock:
            print(f"[DEBUG] remove_job: Acquired lock for: {job.url}")
            
            # Check if it's the current job
            is_current = (self._current_job == job)
            print(f"[DEBUG] remove_job: Is current job? {is_current} for: {job.url}")
            
            # Remove from queue if it's there
            if job in self._jobs:
                self._jobs.remove(job)
                print(f"[DEBUG] remove_job: Removed job from queue: {job.url}")
                return True
            
            # If it's the current job, mark as failed to stop processing
            if is_current:
                print(f"[DEBUG] remove_job: Marking current job as failed: {job.url}")
                job.status = JobStatus.FAILED
                print(f"[DEBUG] remove_job: Job status set to FAILED: {job.url}")
                return True
            
            # If job was popped but not yet set as current, mark as failed to prevent processing
            if job.status == JobStatus.PENDING:
                print(f"[DEBUG] remove_job: Job was popped but not current, marking as failed: {job.url}")
                job.status = JobStatus.FAILED
                print(f"[DEBUG] remove_job: Job status set to FAILED: {job.url}")
                return True
            
            print(f"[DEBUG] remove_job: Job not found in queue or current: {job.url}")
            return False
    
    def get_current_job(self) -> Optional[DownloadJob]:
        """Get the currently downloading job."""
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
                job.status = JobStatus.FAILED
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
                            if queued_job.status == JobStatus.PENDING:
                                job = self._jobs.pop(i)
                                print(f"[DEBUG] Worker: Popped job from queue: {job.url} (status: {job.status})")
                                break
                        
                        if job is not None:
                            break
                        
                        # No jobs available, wait
                        self._condition.wait(timeout=1)
                
                if job is None:
                    continue
                
                # Set as current job
                with self._lock:
                    self._current_job = job
                    print(f"[DEBUG] Worker: Set current job: {job.url} (status: {job.status})")
                
                # Check if job was cancelled while we were getting it
                if job.status == JobStatus.FAILED:
                    print(f"[DEBUG] Worker: Job was cancelled before processing: {job.url}")
                    with self._lock:
                        self._current_job = None
                    continue
                
                # Additional check: if job was removed from UI (status changed to FAILED), skip it
                if job.status == JobStatus.FAILED:
                    print(f"[DEBUG] Worker: Job was marked as failed after popping, skipping: {job.url}")
                    with self._lock:
                        self._current_job = None
                    continue
                
                # Process the job
                print(f"[DEBUG] Worker: Starting to process job: {job.url} (status: {job.status})")
                job.status = JobStatus.DOWNLOADING
                
                try:
                    # Check again before calling downloader
                    if job.status == JobStatus.FAILED:
                        print(f"[DEBUG] Worker: Job cancelled before downloader call: {job.url}")
                        continue
                    
                    print(f"[DEBUG] Worker: Calling downloader for job: {job.url}")
                    self._download_callback(job)
                    
                    # Check if job was cancelled during download
                    if job.status == JobStatus.FAILED:
                        print(f"[DEBUG] Worker: Job was cancelled during download: {job.url}")
                        continue
                    
                    print(f"[DEBUG] Worker: Download completed for job: {job.url}")
                    job.status = JobStatus.COMPLETED
                    
                except Exception as e:
                    print(f"[DEBUG] Worker: Exception during download for {job.url}: {e}")
                    if job.status != JobStatus.FAILED:  # Only set failed if not already cancelled
                        job.status = JobStatus.FAILED
                
                finally:
                    # Clear current job
                    with self._lock:
                        self._current_job = None
                        print(f"[DEBUG] Worker: Cleared current job: {job.url}")
                
            except Exception as e:
                print(f"[DEBUG] Worker: Exception in worker loop: {e}")
                import traceback
                traceback.print_exc()
    
    def update_job_progress(self, job: DownloadJob, progress: float, 
                          eta: Optional[str] = None, speed: Optional[str] = None):
        """
        Update the progress of a job.
        
        Args:
            job: The job to update
            progress: Progress percentage (0-100)
            eta: Estimated time remaining
            speed: Download speed
        """
        if job.status == JobStatus.DOWNLOADING:
            job.progress = max(0.0, min(100.0, progress))
            if eta:
                job.eta = eta
            if speed:
                job.speed = speed
    
    def is_job_processing(self, job: DownloadJob) -> bool:
        """
        Check if a job is currently being processed.
        
        Args:
            job: The job to check
            
        Returns:
            True if the job is currently being processed
        """
        with self._lock:
            return self._current_job == job 