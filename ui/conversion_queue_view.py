"""
Conversion queue view component for YouTube Downloader application.
Displays conversion queue with progress bars and status information.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import List, Callable, Optional
import threading
import os

from core.conversion_queue import ConversionJob, ConversionStatus


class ConversionQueueViewFrame(ttk.Frame):
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
        self.job_widgets = {}  # job -> widget mapping
        self.converting_animation_counter = 0
        self.converting_dots = ["", ".", "..", "..."]
        self.configure(style="ConversionQueueView.TFrame")
        self._create_widgets()
        self._layout_widgets()
        self._setup_styles()
        self._start_animation()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Header
        self.header_frame = ttk.Frame(self, style="ConversionQueueView.TFrame")
        self.title_label = ttk.Label(self.header_frame, text="Conversion", font=("Arial", 17, "bold"), style="ConversionQueueHeading.TLabel")
        self.title_label.pack(side="left")
        
        self.start_button = ttk.Button(
            self.header_frame,
            text="Start Conversions",
            command=self.start_conversions_callback,
            style="Accent.TButton"
        )
        self.start_button.pack(side="right", padx=(8, 0))
        
        self.clear_button = ttk.Button(
            self.header_frame,
            text="Clear All",
            command=self._clear_jobs,
            style="Accent.TButton"
        )
        self.clear_button.pack(side="right")
        
        self.clear_completed_button = ttk.Button(
            self.header_frame,
            text="Clear Completed",
            command=self._clear_completed_jobs,
            style="Accent.TButton"
        )
        self.clear_completed_button.pack(side="right", padx=(0, 8))
        
        # Treeview for jobs
        columns = ('title', 'format', 'destination', 'status')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', selectmode="extended", height=8, style="ConversionQueue.Treeview")
        
        # Configure columns
        self.tree.heading('title', text='File')
        self.tree.heading('format', text='Format')
        self.tree.heading('destination', text='Destination')
        self.tree.heading('status', text='Status')
        
        self.tree.column('title', width=300, anchor='w')
        self.tree.column('format', width=80, anchor='center')
        self.tree.column('destination', width=200, anchor='w')
        self.tree.column('status', width=120, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Progress bar frame (will be populated dynamically)
        self.progress_frame = ttk.Frame(self, style="ConversionQueueView.TFrame")
        
        self.tree.bind('<Button-3>', self._on_item_right_click)
    
    def _layout_widgets(self):
        """Layout all widgets in the frame using grid for top alignment and visible queue."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.configure(height=8)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.tree.bind('<Double-1>', self._on_item_double_click)
    
    def _setup_styles(self):
        """Setup custom styles for the treeview."""
        style = ttk.Style()
        base = '#101216'
        elevated = '#1B1F24'
        accent_gradient = '#FF6EC4'
        accent_gradient2 = '#7873F5'
        success = '#22C55E'
        error = '#EF4444'
        text_pri = '#E8E8E8'
        text_sec = '#A1A1AA'
        
        # Frame and labels
        style.configure('ConversionQueueView.TFrame', background=elevated)
        style.configure('ConversionQueueHeading.TLabel', background=elevated, foreground=text_pri, font=("Arial", 17, "bold"))
        
        # Treeview
        style.configure('ConversionQueue.Treeview',
            background="#23272e",
            fieldbackground="#23272e",
            foreground=text_pri,
            rowheight=36,
            font=("Arial", 14),
            borderwidth=2,
            relief="solid"
        )
        style.map('ConversionQueue.Treeview',
            background=[('selected', accent_gradient2)],
            foreground=[('selected', 'white')]
        )
        
        # Tag-based row colors
        self.tree.tag_configure('pending', background=elevated, foreground=text_pri)
        self.tree.tag_configure('converting', background=elevated, foreground=accent_gradient)
        self.tree.tag_configure('completed', background=elevated, foreground=success)
        self.tree.tag_configure('failed', background=elevated, foreground=error)

        
        # Progress bar styles
        style.configure('Accent.Horizontal.TProgressbar',
            troughcolor=elevated,
            background=accent_gradient2,
            thickness=8,
            borderwidth=0
        )
        style.configure('Success.Horizontal.TProgressbar', background=success)
        style.configure('Error.Horizontal.TProgressbar', background=error)
        
        # Hover effect
        self.tree.bind('<Motion>', self._on_row_hover)
        self.tree.bind('<Leave>', self._on_row_leave)
    
    def add_job(self, job: ConversionJob):
        """
        Add a job to the conversion queue view.
        
        Args:
            job: The conversion job to add
        """
        self.jobs.append(job)
        
        # Create treeview item
        title = job.title or os.path.basename(job.input_path)
        item_id = self.tree.insert('', 'end', values=(
            title,
            job.target_format.upper(),
            job.output_folder,
            self._get_status_text(job)
        ))
        
        # Store mapping
        self.job_widgets[job] = item_id
        
        # Set tag based on status
        self._update_item_tag(job, item_id)
        
        # Update status
        self._update_status()
        
        # Select the new item
        self.tree.selection_set(item_id)
        self.tree.see(item_id)
    
    def update_job(self, job: ConversionJob):
        """
        Update a job's display in the conversion queue view.
        
        Args:
            job: The job to update
        """
        if job not in self.job_widgets:
            return
        
        item_id = self.job_widgets[job]
        
        # Update values
        title = job.title or os.path.basename(job.input_path)
        self.tree.item(item_id, values=(
            title,
            job.target_format.upper(),
            job.output_folder,
            self._get_status_text(job)
        ))
        
        # Update tag
        self._update_item_tag(job, item_id)
        
        # Update status
        self._update_status()
    
    def remove_job(self, job: ConversionJob):
        """
        Remove a job from the conversion queue view.
        
        Args:
            job: The job to remove
        """
        print(f"[DEBUG] Conversion UI: remove_job called for job: {job.title or job.input_path}")
        if job in self.job_widgets:
            item_id = self.job_widgets[job]
            self.tree.delete(item_id)
            del self.job_widgets[job]
        
        if job in self.jobs:
            self.jobs.remove(job)
        
        # Update status
        self._update_status()
        print(f"[DEBUG] Conversion UI: Successfully removed job from UI: {job.title or job.input_path}")
    
    def _update_item_tag(self, job: ConversionJob, item_id: str):
        """Update the tag for a treeview item based on job status."""
        status_tag = job.status.value
        self.tree.item(item_id, tags=(status_tag,))
    
    def _update_status(self):
        """Update the status display."""
        pending_count = len([j for j in self.jobs if j.status == ConversionStatus.PENDING])
        converting_count = len([j for j in self.jobs if j.status == ConversionStatus.CONVERTING])
        completed_count = len([j for j in self.jobs if j.status == ConversionStatus.COMPLETED])
        failed_count = len([j for j in self.jobs if j.status == ConversionStatus.FAILED])
        
        status_text = f"Pending: {pending_count} | Converting: {converting_count} | Completed: {completed_count} | Failed: {failed_count}"
        # You could add a status label here if needed
    
    def _clear_jobs(self):
        """Clear all jobs from the queue except currently converting ones."""
        clearable_jobs = [job for job in self.jobs if job.status != ConversionStatus.CONVERTING]
        if not clearable_jobs:
            messagebox.showinfo("Clear All", "No jobs to clear. Only converting jobs cannot be cleared.")
            return
        result = messagebox.askyesno(
            "Clear All",
            f"Remove {len(clearable_jobs)} job(s) from the queue?"
        )
        if result:
            for job in clearable_jobs:
                if self.remove_job_callback:
                    self.remove_job_callback(job)
                self.remove_job(job)
    
    def _clear_completed_jobs(self):
        """Clear only completed and failed jobs from the queue."""
        completed_jobs = [job for job in self.jobs if job.status in [ConversionStatus.COMPLETED, ConversionStatus.FAILED]]
        if not completed_jobs:
            messagebox.showinfo("Clear Completed", "No completed or failed jobs to clear.")
            return
        result = messagebox.askyesno(
            "Clear Completed",
            f"Remove {len(completed_jobs)} completed/failed job(s) from the queue?"
        )
        if result:
            for job in completed_jobs:
                if self.remove_job_callback:
                    self.remove_job_callback(job)
                self.remove_job(job)
    
    def _on_item_double_click(self, event):
        """Handle double-click on a treeview item."""
        item_id = self.tree.selection()[0] if self.tree.selection() else None
        if item_id:
            job = self._get_job_by_item_id(item_id)
            if job and job.status == ConversionStatus.FAILED:
                # Show error message
                error_msg = job.error_message or "Unknown error"
                messagebox.showerror("Conversion Error", f"Failed to convert {job.title or os.path.basename(job.input_path)}:\n\n{error_msg}")
    
    def _on_item_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            # If the clicked item is not in current selection, select only it
            if item_id not in self.tree.selection():
                self.tree.selection_set(item_id)
            # Get all selected jobs
            selected_jobs = []
            for item_id in self.tree.selection():
                job = self._get_job_by_item_id(item_id)
                if job:
                    selected_jobs.append(job)
            if selected_jobs:
                self._show_context_menu(event, selected_jobs)
    
    def _get_job_by_item_id(self, item_id: str) -> Optional[ConversionJob]:
        """Get a job by its treeview item ID."""
        for job, jid in self.job_widgets.items():
            if jid == item_id:
                return job
        return None
    
    def _show_context_menu(self, event, jobs: List[ConversionJob]):
        """Show context menu for selected jobs."""
        print(f"[DEBUG] Conversion UI: _show_context_menu called with {len(jobs)} jobs")
        menu = tk.Menu(self, tearoff=0)
        
        if len(jobs) == 1:
            # Single selection - show all options
            job = jobs[0]
            print(f"[DEBUG] Conversion UI: Single job selected: {job.title or job.input_path} (status: {job.status})")
            if job.status == ConversionStatus.PENDING:
                menu.add_command(label="Rename Output File...", command=lambda: self._rename_selected_job())
            elif job.status == ConversionStatus.FAILED:
                menu.add_command(label="Retry", command=lambda: self._retry_job(job))
            
            menu.add_separator()
            menu.add_command(label="Remove", command=lambda: self._remove_single_job(job))
        else:
            # Multiple selections - only show remove option
            print(f"[DEBUG] Conversion UI: Multiple jobs selected: {len(jobs)} jobs")
            menu.add_command(label=f"Remove {len(jobs)} Jobs", command=lambda: self._remove_multiple_jobs(jobs))
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _retry_job(self, job: ConversionJob):
        """Retry a failed job."""
        job.status = ConversionStatus.PENDING
        job.progress = 0.0
        job.error_message = None
        self.update_job(job)
    
    def _on_row_hover(self, event):
        """Handle row hover effect."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            # You could add hover effects here
            pass
    
    def _on_row_leave(self, event):
        """Handle row leave event."""
        # You could remove hover effects here
        pass
    
    def _get_status_text(self, job: ConversionJob) -> str:
        """Get the display text for a job's status."""
        if job.status == ConversionStatus.CONVERTING:
            dots = self.converting_dots[self.converting_animation_counter % len(self.converting_dots)]
            return f"Converting{dots}"
        elif job.status == ConversionStatus.PENDING:
            return "Pending"
        elif job.status == ConversionStatus.COMPLETED:
            return "Completed"
        elif job.status == ConversionStatus.FAILED:
            return "Failed"

        else:
            return "Unknown"
    
    def _start_animation(self):
        """Start the converting animation."""
        def animate():
            self.converting_animation_counter += 1
            # Update all converting jobs
            for job in self.jobs:
                if job.status == ConversionStatus.CONVERTING:
                    self.update_job(job)
            self.after(500, animate)
        
        animate()
    
    def set_remove_job_callback(self, callback: Callable[[ConversionJob], None]):
        """Set the callback for removing jobs."""
        self.remove_job_callback = callback
    
    def _rename_selected_job(self):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        job = self._get_job_by_item_id(item_id)
        if not job:
            return
        # Prevent renaming if running or completed
        if job.status in (ConversionStatus.COMPLETED, ConversionStatus.CONVERTING):
            messagebox.showinfo("Rename Not Allowed", "Cannot rename a job that is running or completed.")
            return
        # Suggest current filename
        if job.output_path:
            current_name = os.path.basename(job.output_path)
        elif job.title:
            current_name = job.title
        else:
            current_name = os.path.basename(job.input_path)
        
        # Add extension if not present
        if not os.path.splitext(current_name)[1]:
            current_name += f".{job.target_format}"
        
        base_name, ext = os.path.splitext(current_name)
        
        # Simple dialog for filename without extension (no label for extension)
        new_base = simpledialog.askstring("Rename Output File", "Enter new filename:", initialvalue=base_name)
        if not new_base:
            return
        new_base = new_base.strip()
        if not new_base or any(c in new_base for c in '/\\:*?"<>|'):
            messagebox.showerror("Invalid Filename", "Filename contains invalid characters.")
            return
        new_name = new_base + ext
        # Check for conflicts
        output_folder = getattr(job, 'output_folder', os.getcwd())
        candidate = os.path.join(output_folder, new_name)
        base, ext2 = os.path.splitext(new_name)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(output_folder, f"{base}_{counter}{ext2}")
            counter += 1
        # Update job output_path and title
        job.output_path = candidate
        job.title = os.path.splitext(os.path.basename(candidate))[0]
        # Update UI
        self.update_job(job)
        messagebox.showinfo("Renamed", f"Output file will be: {os.path.basename(candidate)}")
    
    def _remove_single_job(self, job: ConversionJob):
        """Remove a single job from the conversion queue."""
        print(f"[DEBUG] Conversion UI: _remove_single_job called for job: {job.title or job.input_path}")
        
        # Check if job can be removed
        if job.status == ConversionStatus.CONVERTING:
            messagebox.showinfo("Cannot Remove", "Cannot remove a job that is currently converting.")
            return
        
        # Remove from conversion queue if callback is available
        if self.remove_job_callback:
            print(f"[DEBUG] Conversion UI: Calling remove_job_callback for job: {job.title or job.input_path}")
            self.remove_job_callback(job)
        else:
            print(f"[DEBUG] Conversion UI: No remove_job_callback available for job: {job.title or job.input_path}")
        
        # Remove from queue view
        self.remove_job(job)

    def _remove_multiple_jobs(self, jobs: List[ConversionJob]):
        """Remove multiple jobs from the queue."""
        print(f"[DEBUG] Conversion UI: _remove_multiple_jobs called with {len(jobs)} jobs")
        # Filter out jobs that can't be removed (currently converting)
        removable_jobs = [job for job in jobs if job.status != ConversionStatus.CONVERTING]
        non_removable_jobs = [job for job in jobs if job.status == ConversionStatus.CONVERTING]
        
        if non_removable_jobs:
            messagebox.showinfo("Cannot Remove", f"Cannot remove {len(non_removable_jobs)} job(s) that are currently converting.")
        
        if removable_jobs:
            # Remove from conversion queue if callback is available
            for job in removable_jobs:
                if self.remove_job_callback:
                    print(f"[DEBUG] Conversion UI: Calling remove_job_callback for job: {job.title or job.input_path}")
                    self.remove_job_callback(job)
                # Remove from queue view
                self.remove_job(job) 