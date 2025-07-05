"""
Conversion queue view component for YouTube Downloader application.
Displays conversion queue with progress bars and status information.
"""

import customtkinter as ctk
from tkinter import messagebox, simpledialog
from typing import List, Callable, Optional
import threading
import os

from core.conversion_queue import ConversionJob, ConversionStatus


class ConversionJobCard(ctk.CTkFrame):
    """Individual conversion job card for displaying conversion information."""
    
    def __init__(self, parent, job: ConversionJob, cancel_callback: Callable, **kwargs):
        super().__init__(parent, **kwargs)
        self.job = job
        self.cancel_callback = cancel_callback
        
        # Create layout
        self.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        self.status_label = ctk.CTkLabel(self, text="", width=20, height=20)
        self.status_label.grid(row=0, column=0, padx=(10, 10), pady=10, sticky="n")
        
        # Main content
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        self.title_label = ctk.CTkLabel(content_frame, text=job.title or os.path.basename(job.input_path), font=("Segoe UI", 12, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Details
        details_frame = ctk.CTkFrame(content_frame)
        details_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.format_label = ctk.CTkLabel(details_frame, text=f"Format: {job.target_format.upper()}", font=("Segoe UI", 10))
        self.format_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        self.destination_label = ctk.CTkLabel(details_frame, text=f"Destination: {job.output_folder}", font=("Segoe UI", 10))
        self.destination_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        self.status_text_label = ctk.CTkLabel(details_frame, text="Pending", font=("Segoe UI", 10))
        self.status_text_label.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(content_frame)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.progress_bar.set(0)
        
        # Actions
        actions_frame = ctk.CTkFrame(content_frame)
        actions_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.cancel_button = ctk.CTkButton(actions_frame, text="Cancel", command=lambda: self.cancel_callback(job), width=80)
        self.cancel_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.update_display()
    
    def update_display(self):
        """Update the display based on job status."""
        # Update status indicator
        if self.job.status == ConversionStatus.PENDING:
            self.status_label.configure(text="⏳", text_color="#fbbf24")
        elif self.job.status == ConversionStatus.CONVERTING:
            self.status_label.configure(text="��", text_color="#00d4ff")
        elif self.job.status == ConversionStatus.COMPLETED:
            self.status_label.configure(text="✅", text_color="#4ade80")
        elif self.job.status == ConversionStatus.FAILED:
            self.status_label.configure(text="❌", text_color="#f87171")
        
        # Update status text
        status_text = self._get_status_text(self.job)
        self.status_text_label.configure(text=status_text)
        
        # Update progress
        if hasattr(self.job, 'progress'):
            self.progress_bar.set(self.job.progress / 100)
        
        # Update button visibility
        if self.job.status in [ConversionStatus.CONVERTING, ConversionStatus.PENDING]:
            self.cancel_button.configure(state="normal")
        else:
            self.cancel_button.configure(state="disabled")
    
    def _get_status_text(self, job: ConversionJob) -> str:
        """Get status text for a job."""
        if job.status == ConversionStatus.PENDING:
            return "Pending"
        elif job.status == ConversionStatus.CONVERTING:
            progress = getattr(job, 'progress', 0)
            return f"Converting {progress:.1f}%"
        elif job.status == ConversionStatus.COMPLETED:
            return "Completed"
        elif job.status == ConversionStatus.FAILED:
            return "Failed"
        return "Unknown"


class ConversionQueueViewFrame(ctk.CTkFrame):
    """
    Conversion queue view frame displaying conversion jobs with progress tracking.
    """
    
    def __init__(self, parent, cancel_job_callback: Callable[[ConversionJob], None], start_conversions_callback: Callable[[], None]):
        """
        Initialize the conversion queue view frame.
        
        Args:
            parent: Parent widget
            cancel_job_callback: Callback function to cancel a job
            start_conversions_callback: Callback function to start conversions
        """
        super().__init__(parent)
        self.cancel_job_callback = cancel_job_callback
        self.start_conversions_callback = start_conversions_callback
        self.remove_job_callback = None  # Will be set by main application
        self.jobs: List[ConversionJob] = []
        self.job_cards = {}  # job -> card mapping
        self.converting_animation_counter = 0
        self.converting_dots = ["", ".", "..", "..."]
        self._create_widgets()
        self._layout_widgets()
        self._start_animation()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.title_label = ctk.CTkLabel(self.header_frame, text="Conversion", font=("Segoe UI", 18, "bold"))
        self.title_label.pack(side="left")
        
        self.start_button = ctk.CTkButton(
            self.header_frame,
            text="Start Conversions",
            command=self.start_conversions_callback,
            font=("Segoe UI", 11)
        )
        self.start_button.pack(side="right", padx=(8, 0))
        
        self.clear_button = ctk.CTkButton(
            self.header_frame,
            text="Clear All",
            command=self._clear_jobs,
            font=("Segoe UI", 11)
        )
        self.clear_button.pack(side="right")
        
        self.clear_completed_button = ctk.CTkButton(
            self.header_frame,
            text="Clear Completed",
            command=self._clear_completed_jobs,
            font=("Segoe UI", 11)
        )
        self.clear_completed_button.pack(side="right", padx=(0, 8))
        
        # Scrollable frame for job cards
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        
        # Progress bar frame (will be populated dynamically)
        self.progress_frame = ctk.CTkFrame(self)
    
    def _layout_widgets(self):
        """Layout all widgets in the frame using grid for top alignment and visible queue."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew")
        
        # Bind events
        self.scrollable_frame.bind('<Button-3>', self._on_item_right_click)
    
    def add_job(self, job: ConversionJob):
        """
        Add a job to the conversion queue view.
        
        Args:
            job: The conversion job to add
        """
        self.jobs.append(job)
        
        # Create job card
        job_card = ConversionJobCard(self.scrollable_frame, job, self.cancel_job_callback)
        job_card.pack(fill="x", padx=10, pady=5)
        
        # Store mapping
        self.job_cards[job] = job_card
        
        # Update status
        self._update_status()
        
        # Select the new item
        job_card.focus_set()
    
    def update_job(self, job: ConversionJob):
        """
        Update a job's display in the conversion queue view.
        
        Args:
            job: The job to update
        """
        if job in self.job_cards:
            self.job_cards[job].update_display()
    
    def remove_job(self, job: ConversionJob):
        """
        Remove a job from the conversion queue view.
        
        Args:
            job: The job to remove
        """
        if job in self.job_cards:
            self.job_cards[job].destroy()
            del self.job_cards[job]
        if job in self.jobs:
            self.jobs.remove(job)
        self._update_status()
    
    def _update_status(self):
        """Update the status display."""
        total_jobs = len(self.jobs)
        completed_jobs = len([j for j in self.jobs if j.status == ConversionStatus.COMPLETED])
        failed_jobs = len([j for j in self.jobs if j.status == ConversionStatus.FAILED])
        active_jobs = len([j for j in self.jobs if j.status == ConversionStatus.CONVERTING])
        
        status_text = f"Total: {total_jobs} | Active: {active_jobs} | Completed: {completed_jobs} | Failed: {failed_jobs}"
        print(f"[DEBUG] Conversion queue status: {status_text}")
    
    def _clear_jobs(self):
        """Clear all jobs from the queue."""
        if not self.jobs:
            return
        
        result = messagebox.askyesno("Clear All Jobs", "Are you sure you want to clear all conversion jobs from the queue?")
        if result:
            # Cancel all active jobs
            for job in self.jobs:
                if job.status in [ConversionStatus.PENDING, ConversionStatus.CONVERTING]:
                    self.cancel_job_callback(job)
            
            # Clear all job cards
            for card in self.job_cards.values():
                card.destroy()
            
            self.job_cards.clear()
            self.jobs.clear()
            self._update_status()
    
    def _clear_completed_jobs(self):
        """Clear completed jobs from the queue."""
        completed_jobs = [j for j in self.jobs if j.status == ConversionStatus.COMPLETED]
        if not completed_jobs:
            return
        
        result = messagebox.askyesno("Clear Completed Jobs", f"Are you sure you want to clear {len(completed_jobs)} completed conversion jobs?")
        if result:
            for job in completed_jobs:
                self.remove_job(job)
    
    def _on_item_right_click(self, event):
        """Handle right-click on items."""
        # For now, we'll implement a simple context menu
        pass
    
    def _on_item_double_click(self, event):
        """Handle double-click on items."""
        # For now, we'll implement a simple double-click handler
        pass
    
    def _get_job_by_item_id(self, item_id: str) -> Optional[ConversionJob]:
        """Get job by treeview item ID."""
        # This method is no longer needed with the card-based approach
        return None
    
    def _retry_job(self, job: ConversionJob):
        """Retry a failed job."""
        if job.status == ConversionStatus.FAILED:
            job.status = ConversionStatus.PENDING
            self.update_job(job)
    
    def _start_animation(self):
        """Start the converting animation."""
        def animate():
            if self.converting_animation_counter < len(self.converting_dots) - 1:
                self.converting_animation_counter += 1
            else:
                self.converting_animation_counter = 0
            
            # Update all converting jobs
            for job in self.jobs:
                if job.status == ConversionStatus.CONVERTING:
                    self.update_job(job)
            
            # Schedule next animation frame
            self.after(500, animate)
        
        # Start animation
        self.after(500, animate)
    
    def set_remove_job_callback(self, callback: Callable[[ConversionJob], None]):
        """Set the callback for removing jobs."""
        self.remove_job_callback = callback
    
    def _show_context_menu(self, event, jobs: List[ConversionJob]):
        """Show context menu for selected jobs."""
        # Simplified context menu - just show basic info
        if len(jobs) == 1:
            job = jobs[0]
            messagebox.showinfo("Job Info", f"Title: {job.title}\nStatus: {job.status.value}\nInput: {job.input_path}")
        else:
            messagebox.showinfo("Selected Jobs", f"{len(jobs)} conversion jobs selected")
    
    def _rename_selected_job(self):
        """Rename the selected job."""
        # This functionality can be implemented later
        pass
    
    def _remove_single_job(self, job: ConversionJob):
        """Remove a single job."""
        if self.remove_job_callback:
            self.remove_job_callback(job)
        self.remove_job(job)
    
    def _remove_multiple_jobs(self, jobs: List[ConversionJob]):
        """Remove multiple jobs."""
        for job in jobs:
            if self.remove_job_callback:
                self.remove_job_callback(job)
            self.remove_job(job) 