"""
Queue view component for YouTube Downloader application.
Displays download queue with progress bars and status information.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import List, Callable, Optional
import threading
import os

from core.queue import DownloadJob, JobStatus


class QueueViewFrame(ttk.Frame):
    """
    Queue view frame displaying download jobs with progress tracking.
    """
    
    def __init__(self, parent, cancel_job_callback: Callable[[DownloadJob], None], start_downloads_callback: Callable[[], None]):
        """
        Initialize the queue view frame.
        
        Args:
            parent: Parent widget
            cancel_job_callback: Callback function to cancel a job
            start_downloads_callback: Callback function to start downloads
        """
        super().__init__(parent)
        self.cancel_job_callback = cancel_job_callback
        self.start_downloads_callback = start_downloads_callback
        self.remove_job_callback = None  # Will be set by main application
        self.jobs: List[DownloadJob] = []
        self.job_widgets = {}  # item_id -> job mapping
        self.downloading_animation_counter = 0
        self.downloading_dots = ["", ".", "..", "..."]
        self.configure(style="QueueView.TFrame")
        self._create_widgets()
        self._layout_widgets()
        self._setup_styles()
        self._start_animation()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Header
        self.header_frame = ttk.Frame(self, style="QueueView.TFrame")
        self.title_label = ttk.Label(self.header_frame, text="Downloads", font=("Arial", 17, "bold"), style="QueueHeading.TLabel")
        self.title_label.pack(side="left")
        
        self.start_button = ttk.Button(
            self.header_frame,
            text="Start Downloads",
            command=self.start_downloads_callback,
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
        columns = ('title', 'format', 'compatibility', 'destination', 'status')
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended", height=10, style="Queue.Treeview")
        
        # Configure columns
        self.tree.heading('title', text='Title')
        self.tree.heading('format', text='Format')
        self.tree.heading('compatibility', text='Compatibility')
        self.tree.heading('destination', text='Destination')
        self.tree.heading('status', text='Status')
        
        self.tree.column('title', width=300, anchor='w')
        self.tree.column('format', width=80, anchor='center')
        self.tree.column('compatibility', width=120, anchor='center')
        self.tree.column('destination', width=200, anchor='w')
        self.tree.column('status', width=120, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Progress bar frame (will be populated dynamically)
        self.progress_frame = ttk.Frame(self, style="QueueView.TFrame")
    
    def _layout_widgets(self):
        """Layout all widgets in the frame using grid for top alignment and visible queue."""
        print("Laying out widgets in QueueViewFrame...")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.configure(height=10)
        print("Treeview created and gridded.")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.tree.bind('<Double-1>', self._on_item_double_click)
        self.tree.bind('<Button-3>', self._on_item_right_click)
    
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
        style.configure('QueueView.TFrame', background=elevated)
        style.configure('QueueHeading.TLabel', background=elevated, foreground=text_pri, font=("Inter", 17, "bold"))
        # Treeview
        style.configure('Queue.Treeview',
            background="#23272e",
            fieldbackground="#23272e",
            foreground=text_pri,
            rowheight=36,
            font=("Inter", 14),
            borderwidth=2,
            relief="solid"
        )
        style.map('Queue.Treeview',
            background=[('selected', accent_gradient2)],
            foreground=[('selected', 'white')]
        )
        # Tag-based row colors
        self.tree.tag_configure('pending', background=elevated, foreground=text_pri)
        self.tree.tag_configure('downloading', background=elevated, foreground=accent_gradient)
        self.tree.tag_configure('completed', background=elevated, foreground=success)
        self.tree.tag_configure('failed', background=elevated, foreground=error)
        self.tree.tag_configure('cancelled', background=elevated, foreground=text_sec)
        # Progress bar styles
        style.configure('Accent.Horizontal.TProgressbar',
            troughcolor=elevated,
            background=accent_gradient2,
            thickness=8,
            borderwidth=0
        )
        style.configure('Success.Horizontal.TProgressbar', background=success)
        style.configure('Error.Horizontal.TProgressbar', background=error)
        # Hover effect (simulate with tag on row enter/leave)
        self.tree.bind('<Motion>', self._on_row_hover)
        self.tree.bind('<Leave>', self._on_row_leave)
    
    def add_job(self, job: DownloadJob):
        """
        Add a job to the queue view.
        
        Args:
            job: The download job to add
        """
        self.jobs.append(job)
        
        # Create treeview item
        title = job.title or "Loading..."
        item_id = self.tree.insert('', 'end', values=(
            title,
            job.format.upper(),
            "Yes" if getattr(job, 'compatibility_mode', False) else "No",
            job.output_folder,
            self._get_status_text(job)
        ))
        
        # Store mapping
        self.job_widgets[item_id] = job
        
        # Set tag based on status
        self._update_item_tag(job, item_id)
        
        # Update status
        self._update_status()
        
        # Select the new item
        self.tree.selection_set(item_id)
        self.tree.see(item_id)
    
    def update_job(self, job: DownloadJob):
        """
        Update a job's display in the queue view.
        
        Args:
            job: The job to update
        """
        # Find the item_id for this job
        item_id = None
        for iid, j in self.job_widgets.items():
            if j == job:
                item_id = iid
                break
        if not item_id:
            return
        
        # Update values
        title = job.title or "Loading..."
        self.tree.item(item_id, values=(
            title,
            job.format.upper(),
            "Yes" if getattr(job, 'compatibility_mode', False) else "No",
            job.output_folder,
            self._get_status_text(job)
        ))
        
        # Update tag
        self._update_item_tag(job, item_id)
        
        # Update status
        self._update_status()
    
    def remove_job(self, job: DownloadJob):
        """
        Remove a job from the queue view.
        
        Args:
            job: The job to remove
        """
        # Find the item_id for this job
        item_id = None
        for iid, j in self.job_widgets.items():
            if j == job:
                item_id = iid
                break
        if item_id:
            self.tree.delete(item_id)
            del self.job_widgets[item_id]
        if job in self.jobs:
            self.jobs.remove(job)
        self._update_status()
    
    def _cleanup_orphaned_widgets(self):
        """Clean up any orphaned job_widgets entries that don't exist in the treeview."""
        orphaned_jobs = []
        for job, item_id in list(self.job_widgets.items()):
            try:
                # Check if the item still exists in the treeview
                self.tree.item(item_id)
            except tk.TclError:
                # Item doesn't exist in treeview, mark for removal
                orphaned_jobs.append(job)
        
        for job in orphaned_jobs:
            print(f"[DEBUG] UI: Removing orphaned job_widgets entry: {job.url}")
            del self.job_widgets[job]
    
    def _rebuild_job_widgets_mapping(self):
        """Rebuild the job_widgets mapping to ensure consistency."""
        print(f"[DEBUG] UI: Rebuilding job_widgets mapping")
        self.job_widgets.clear()
        
        # Get all items in the treeview
        for item_id in self.tree.get_children():
            # Try to find a job that matches this item
            for job in self.jobs:
                # Create a temporary mapping to check if this job should be associated with this item
                # This is a heuristic approach - we'll use the job's position in the jobs list
                job_index = self.jobs.index(job)
                tree_children = self.tree.get_children()
                if job_index < len(tree_children) and tree_children[job_index] == item_id:
                    self.job_widgets[item_id] = job
                    print(f"[DEBUG] UI: Rebuilt mapping: {job.url} -> {item_id}")
                    break
        
        print(f"[DEBUG] UI: Rebuilt mapping contains {len(self.job_widgets)} entries")
    
    def _update_item_tag(self, job: DownloadJob, item_id: str):
        """Update the tag of a treeview item based on job status."""
        tag = job.status.value
        self.tree.item(item_id, tags=(tag,))
    
    def _update_status(self):
        """Update the status bar."""
        total = len(self.jobs)
        pending = sum(1 for job in self.jobs if job.status == JobStatus.PENDING)
        downloading = sum(1 for job in self.jobs if job.status == JobStatus.DOWNLOADING)
        completed = sum(1 for job in self.jobs if job.status == JobStatus.COMPLETED)
        failed = sum(1 for job in self.jobs if job.status == JobStatus.FAILED)
        
        status_text = f"Total: {total} | Pending: {pending} | Downloading: {downloading} | Completed: {completed} | Failed: {failed}"
    
    def _clear_jobs(self):
        """Clear all jobs from the queue except currently downloading ones."""
        clearable_jobs = [job for job in self.jobs if job.status != JobStatus.DOWNLOADING]
        if not clearable_jobs:
            messagebox.showinfo("Clear All", "No jobs to clear. Only downloading jobs cannot be cleared.")
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
    
    def _on_item_double_click(self, event):
        """Handle double-click on a queue item."""
        item_id = self.tree.selection()[0]
        job = self._get_job_by_item_id(item_id)
        
        if job and job.status == JobStatus.FAILED:
            # Show error details
            messagebox.showerror(
                "Download Error",
                f"Error: {job.error_message or 'Unknown error'}"
            )
    
    def _on_item_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            # If the clicked item is not in current selection, select only it
            if row_id not in self.tree.selection():
                self.tree.selection_set(row_id)
            # Get all selected jobs
            selected_jobs = []
            for item_id in self.tree.selection():
                job = self._get_job_by_item_id(item_id)
                if job:
                    selected_jobs.append(job)
            if selected_jobs:
                self._show_context_menu(event, selected_jobs)
    
    def _get_job_by_item_id(self, item_id: str) -> Optional[DownloadJob]:
        """Get job by treeview item ID."""
        return self.job_widgets.get(item_id)
    
    def _retry_job(self, job: DownloadJob):
        """Retry a failed job."""
        # Reset job status
        job.status = JobStatus.PENDING
        job.progress = 0.0
        job.error_message = None
        job.eta = None
        job.speed = None
        
        # Update display
        self.update_job(job)

    def _on_row_hover(self, event):
        rowid = self.tree.identify_row(event.y)
        if rowid:
            self.tree.tag_configure('hover', background="#23272e")
            tags = self.tree.item(rowid, 'tags')
            if not isinstance(tags, tuple):
                tags = (tags,) if tags else ()
            if 'hover' not in tags:
                self.tree.item(rowid, tags=tags + ('hover',))

    def _on_row_leave(self, event):
        for rowid in self.tree.get_children():
            tags = tuple(tag for tag in self.tree.item(rowid, 'tags') if tag != 'hover')
            self.tree.item(rowid, tags=tags)

    def _get_status_text(self, job: DownloadJob) -> str:
        """Get the status text for a job, with animation for downloading."""
        if job.status == JobStatus.DOWNLOADING:
            return f"Downloading{self.downloading_dots[self.downloading_animation_counter % len(self.downloading_dots)]}"
        else:
            return job.status.value.title()
    
    def _start_animation(self):
        """Start the downloading animation timer."""
        def animate():
            self.downloading_animation_counter += 1
            # Update all downloading jobs
            for job in self.jobs:
                if job.status == JobStatus.DOWNLOADING:
                    self.update_job(job)
            # Also update all non-downloading jobs to refresh their status
            for job in self.jobs:
                if job.status != JobStatus.DOWNLOADING:
                    self.update_job(job)
            # Schedule next animation frame
            self.after(500, animate)
        
        # Start the animation loop
        self.after(500, animate)
    
    def _clear_completed_jobs(self):
        """Clear only completed and failed jobs from the queue."""
        completed_jobs = [job for job in self.jobs if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]]
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

    def set_remove_job_callback(self, callback: Callable[[DownloadJob], None]):
        """Set the callback for removing jobs from the download queue."""
        self.remove_job_callback = callback 

    def _show_context_menu(self, event, jobs: List[DownloadJob]):
        """Show context menu for selected jobs."""
        print(f"[DEBUG] UI: _show_context_menu called with {len(jobs)} jobs")
        menu = tk.Menu(self, tearoff=0)
        
        if len(jobs) == 1:
            # Single selection - show all options
            job = jobs[0]
            print(f"[DEBUG] UI: Single job selected: {job.url} (status: {job.status})")
            if job.status == JobStatus.PENDING:
                menu.add_command(label="Rename Output File...", command=lambda: self._rename_selected_job())
            elif job.status == JobStatus.FAILED:
                menu.add_command(label="Retry", command=lambda: self._retry_job(job))
            
            menu.add_separator()
            menu.add_command(label="Remove", command=lambda: self._remove_single_job(job))
        else:
            # Multiple selections - only show remove option
            print(f"[DEBUG] UI: Multiple jobs selected: {len(jobs)} jobs")
            menu.add_command(label=f"Remove {len(jobs)} Jobs", command=lambda: self._remove_multiple_jobs(jobs))
        
        menu.tk_popup(event.x_root, event.y_root)

    def _rename_selected_job(self):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        job = self._get_job_by_item_id(item_id)
        if not job:
            return
        # Prevent renaming if running or completed
        if getattr(job, 'status', None) in (getattr(job, 'COMPLETED', None), getattr(job, 'DOWNLOADING', None)):
            messagebox.showinfo("Rename Not Allowed", "Cannot rename a job that is running or completed.")
            return
        # Suggest current filename
        current_name = os.path.basename(getattr(job, 'output_path', '') or getattr(job, 'title', 'output'))
        ext = os.path.splitext(current_name)[1]
        new_name = simpledialog.askstring("Rename Output File", f"Enter new filename:", initialvalue=current_name)
        if not new_name:
            return
        # Validate filename
        new_name = new_name.strip()
        if not new_name or any(c in new_name for c in '/\\:*?"<>|'):
            messagebox.showerror("Invalid Filename", "Filename contains invalid characters.")
            return
        # Ensure extension
        if not os.path.splitext(new_name)[1]:
            new_name += ext
        # Check for conflicts
        output_folder = getattr(job, 'output_folder', os.getcwd())
        candidate = os.path.join(output_folder, new_name)
        base, ext = os.path.splitext(new_name)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(output_folder, f"{base}_{counter}{ext}")
            counter += 1
        # Update job output path and title
        # job.output_path = candidate  # Remove this line, DownloadJob has no output_path
        job.title = os.path.splitext(os.path.basename(candidate))[0]
        job.custom_title = job.title  # Mark as manually renamed
        # Update UI
        self.update_job(job)
        messagebox.showinfo("Renamed", f"Output file will be: {os.path.basename(candidate)}")

    def _remove_single_job(self, job: DownloadJob):
        """Remove a single job from the queue."""
        print(f"[DEBUG] UI: _remove_single_job called for job: {job.url}")
        
        # Check if job can be removed
        if job.status == JobStatus.DOWNLOADING:
            messagebox.showinfo("Cannot Remove", "Cannot remove a job that is currently downloading.")
            return
        
        # Remove from download queue if callback is available
        if self.remove_job_callback:
            print(f"[DEBUG] UI: Calling remove_job_callback for job: {job.url}")
            self.remove_job_callback(job)
        else:
            print(f"[DEBUG] UI: No remove_job_callback available for job: {job.url}")
        
        # Remove from queue view
        self.remove_job(job)

    def _remove_multiple_jobs(self, jobs: List[DownloadJob]):
        """Remove multiple jobs from the queue."""
        print(f"[DEBUG] UI: _remove_multiple_jobs called with {len(jobs)} jobs")
        # Filter out jobs that can't be removed (currently downloading)
        removable_jobs = [job for job in jobs if job.status != JobStatus.DOWNLOADING]
        non_removable_jobs = [job for job in jobs if job.status == JobStatus.DOWNLOADING]
        
        if non_removable_jobs:
            messagebox.showinfo("Cannot Remove", f"Cannot remove {len(non_removable_jobs)} job(s) that are currently downloading.")
        
        if removable_jobs:
            # Remove from download queue if callback is available
            for job in removable_jobs:
                if self.remove_job_callback:
                    print(f"[DEBUG] UI: Calling remove_job_callback for job: {job.url}")
                    self.remove_job_callback(job)
                # Remove from queue view
                self.remove_job(job)

    def _add_to_queue(self, url, format_type, *args, **kwargs):
        print(f"[DEBUG] UI: _add_to_queue called with url={url}, format_type={format_type}")
        # ... existing code ... 