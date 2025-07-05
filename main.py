"""
Main application for YouTube Downloader.
Integrates all components and provides the main window.
"""

import customtkinter as ctk
from tkinter import messagebox
import os
import json
import threading
import sys
from pathlib import Path
import traceback

# Explicit imports for PyInstaller bundling
import core.utils
import core.queue
import core.downloader
import core.converter
import core.first_launch
import core.yt_dlp_installer
import core.conversion_queue
import ui.sidebar
import ui.queue_view
import ui.conversion_queue_view
import ui.update_dialog

from core.queue import DownloadQueue, DownloadJob, JobStatus
from core.conversion_queue import ConversionQueue, ConversionJob, ConversionStatus
from core.downloader import Downloader
from core.converter import FileConverter
from core.utils import safe_error_message, resource_path
from core.first_launch import FirstLaunchManager
from core.yt_dlp_installer import InstallerStatus
from ui.sidebar import SidebarFrame
from ui.queue_view import QueueViewFrame
from ui.conversion_queue_view import ConversionQueueViewFrame
from ui.update_dialog import UpdateDialog, UpdateNotificationDialog


class BigGayDownloader:
    """
    Main application class for Big Gay Downloader.
    """
    
    def __init__(self):
        """Initialize the application."""
        # Configure CustomTkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("Big Gay Downloader - Advanced Media Processor")
        self.root.geometry("1600x900")  # Larger for high-tech layout
        self.root.minsize(1400, 700)
        
        # Set window icon
        try:
            # Try different paths for icon (development vs built)
            icon_paths = [
                resource_path('assets/icon.png'),  # PNG preferred for iconphoto
                resource_path('assets/icon.ico'),  # ICO fallback
            ]
            icon_set = False
            for icon_path in icon_paths:
                if Path(icon_path).exists():
                    if icon_path.lower().endswith('.ico'):
                        self.root.iconbitmap(icon_path)
                        icon_set = True
                        break
                    elif icon_path.lower().endswith('.png'):
                        try:
                            # CustomTkinter doesn't support iconphoto the same way as Tkinter
                            # We'll skip icon setting for PNG files in CustomTkinter
                            icon_set = True
                            break
                        except Exception as e:
                            print(f"Could not load PNG icon: {e}")
                            continue
            if not icon_set:
                print("Could not find or load icon file")
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Initialize components
        self.downloader = Downloader()
        self.file_converter = FileConverter()
        self.download_queue = DownloadQueue(self._download_job)
        self.conversion_queue = ConversionQueue(self._convert_job)
        
        # Initialize first launch manager
        self.first_launch_manager = FirstLaunchManager()
        
        # Load configuration
        self.config = self._load_config()
        
        # Setup UI
        self._setup_ui()
        
        # Center the window on screen (after UI setup for accurate dimensions)
        self._center_window()
        
        # Setup UI update timer
        self._setup_ui_updates()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Check for first launch and yt-dlp installation
        self._check_first_launch()
        
        self.downloads_running = False
        self.conversions_running = False
        self._cleanup_counter = 0  # Initialize cleanup counter
    
    def _center_window(self):
        """Center the window on the screen."""
        # Update the window to get accurate dimensions
        self.root.update_idletasks()
        
        # Get window dimensions
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate position to center the window
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set window position
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def _load_config(self) -> dict:
        """Load application configuration."""
        config_path = Path.home() / ".simple_ytdl" / "config.json"
        default_config = {
            "output_folder": str(Path.home() / "Downloads"),
            "last_format": "mp4"
        }
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception:
            pass
        
        return default_config
    
    def _save_config(self):
        """Save application configuration."""
        config_path = Path.home() / ".simple_ytdl" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
    
    def _setup_ui(self):
        """Setup the main UI."""
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Sidebar (increased width for better proportions)
        self.sidebar = SidebarFrame(
            self.root,
            self._add_job_to_queue,
            self.config.get("output_folder", ""),
            self._on_output_folder_changed,
            self._add_conversion_job_to_queue
        )
        self.sidebar.set_update_callback(self._handle_update_button_click)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(32, 0), pady=32)

        # Main content area (increased width for better balance)
        self.main_content = ctk.CTkFrame(self.root, width=1000)
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=(32, 32), pady=32)
        self.main_content.grid_propagate(False)
        self.main_content.columnconfigure(0, weight=1)
        self.main_content.rowconfigure(0, weight=1)
        self.main_content.rowconfigure(1, weight=1)

        # Download queue view (top)
        self.download_queue_view = QueueViewFrame(
            self.main_content,
            self._cancel_job,
            self._start_downloads
        )
        self.download_queue_view.set_remove_job_callback(self._remove_job_from_queue)
        self.download_queue_view.grid(row=0, column=0, sticky="nsew", pady=(0, 16))

        # Conversion queue view (bottom)
        self.conversion_queue_view = ConversionQueueViewFrame(
            self.main_content,
            self._cancel_conversion_job,
            self._start_conversions
        )
        self.conversion_queue_view.set_remove_job_callback(self._remove_conversion_job_from_queue)
        self.conversion_queue_view.grid(row=1, column=0, sticky="nsew")

        # Update sidebar with saved configuration
        self._update_sidebar_from_config()
    
    def _check_first_launch(self):
        """Check for first launch and handle yt-dlp installation."""
        if self.first_launch_manager.should_install_yt_dlp():
            self._show_installation_dialog()
        else:
            # Check for updates in the background
            self._check_for_updates_background()
    
    def _show_installation_dialog(self):
        """Show installation dialog for first launch."""
        from tkinter import messagebox
        
        result = messagebox.askyesno(
            "Welcome to Big Gay Downloader",
            "This is your first time running the application.\n\n"
            "yt-dlp needs to be installed to download YouTube videos.\n\n"
            "Would you like to install it now?",
            icon=messagebox.QUESTION
        )
        
        if result:
            self._install_yt_dlp_on_first_launch()
        else:
            messagebox.showwarning(
                "Installation Required",
                "yt-dlp is required to download videos.\n"
                "You can install it later using the 'Update yt-dlp' button."
            )
    
    def _install_yt_dlp_on_first_launch(self):
        """Install yt-dlp on first launch."""
        def progress_callback(status: InstallerStatus, progress: float, message: str):
            # Update status in the main window title
            self.root.title(f"Big Gay Downloader - Installing yt-dlp... {progress:.1f}%")
        
        def completion_callback(success: bool, message: str):
            if success:
                self.root.title("Big Gay Downloader")
                messagebox.showinfo(
                    "Installation Complete! 🎉", 
                    f"yt-dlp has been installed successfully!\n\n"
                    f"yt-dlp is a powerful video downloader that enables this application to download videos from YouTube and other platforms.\n\n"
                    f"You can now:\n"
                    f"• Download videos from YouTube and XVideos\n"
                    f"• Convert videos to MP3 or MP4 format\n"
                    f"• Use all the features of Big Gay Downloader\n\n"
                    f"Welcome to the app! 🏳️‍🌈"
                )
            else:
                self.root.title("Big Gay Downloader")
                print('ERROR: Installation Failed')
                traceback.print_exc()
                messagebox.showerror("Installation Failed", f"Failed to install yt-dlp:\n\n{message}")
        
        self.first_launch_manager.install_yt_dlp_async(progress_callback, completion_callback)
    
    def _check_for_updates_background(self):
        """Check for yt-dlp updates in the background."""
        def check_updates():
            try:
                update_info = self.first_launch_manager.check_for_updates()
                if update_info.get("update_available", False):
                    # Show update notification in main thread
                    self.root.after(0, self._show_update_notification, update_info)
            except Exception as e:
                print(f"[DEBUG] Background update check failed: {e}")
        
        # Run in background thread
        import threading
        thread = threading.Thread(target=check_updates, daemon=True)
        thread.start()
    
    def _show_update_notification(self, update_info: dict):
        """Show update notification dialog."""
        def update_callback():
            # Create simple progress and completion callbacks for the update
            def progress_callback(status: InstallerStatus, progress: float, message: str):
                print(f"Update progress: {progress:.1f}% - {message}")
            
            def completion_callback(success, message):
                if success:
                    print("Update completed successfully")
                    messagebox.showinfo("Update Complete", f"yt-dlp has been updated successfully!\n\n{message}")
                else:
                    print(f"Update failed: {message}")
                    messagebox.showerror("Update Failed", f"Failed to update yt-dlp:\n\n{message}")
            
            self.first_launch_manager.update_yt_dlp_async(progress_callback, completion_callback)
        
        UpdateNotificationDialog(
            self.root,
            update_info["current_version"],
            update_info["latest_version"],
            update_callback
        )
    
    def _handle_update_button_click(self):
        """Handle update button click from sidebar."""
        try:
            update_info = self.first_launch_manager.check_for_updates()
            
            if update_info.get("update_available", False):
                def update_callback(progress_callback, completion_callback):
                    self.first_launch_manager.update_yt_dlp_async(progress_callback, completion_callback)
                
                UpdateDialog(
                    self.root,
                    update_info["current_version"],
                    update_info["latest_version"]
                )
            else:
                from tkinter import messagebox
                messagebox.showinfo(
                    "No Updates Available",
                    "Your application is up to date!"
                )
        except Exception as e:
            from tkinter import messagebox
            print('ERROR: <context for line 345>')
            traceback.print_exc()
            messagebox.showerror(
                "Update Check Failed",
                f"Failed to check for updates:\n\n{str(e)}"
            )
    
    def _update_sidebar_from_config(self):
        """Update sidebar display with saved configuration."""
        saved_folder = self.config.get("output_folder", "")
        if saved_folder and os.path.exists(saved_folder):
            self.sidebar.set_output_folder(saved_folder)
    
    def _on_output_folder_changed(self, new_folder: str):
        """Handle output folder change from sidebar."""
        self.config["output_folder"] = new_folder
        self._save_config()
    
    def _add_conversion_job_to_queue(self, input_path: str, target_format: str, output_folder: str):
        """
        Add a conversion job to the conversion queue.
        
        Args:
            input_path: Path to the input file
            target_format: Target format ('mp4' or 'mp3')
            output_folder: Output folder path
        """
        # Create conversion job
        job = ConversionJob(
            input_path=input_path,
            target_format=target_format,
            output_folder=output_folder,
            title=os.path.basename(input_path)
        )
        
        # Check if queue is full
        if self.conversion_queue.is_queue_full():
            print('ERROR: Conversion queue full')
            traceback.print_exc()
            messagebox.showerror("Queue Full", f"Conversion queue is full (maximum {self.conversion_queue.get_queue_capacity()} jobs). Please wait for some conversions to complete.")
            return
        
        # Add to conversion queue view
        self.conversion_queue_view.add_job(job)
        
        # Add to conversion queue
        if not self.conversion_queue.add_job(job):
            print('ERROR: Failed to add conversion job to queue')
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to add conversion job to queue")
            return
        
        print(f"Conversion job added successfully. Queue size: {self.conversion_queue.get_queue_size()}")
        
        # Check if conversions are currently running
        if not self.conversions_running:
            print("[DEBUG] Conversions not running - user must click 'Start Conversions' to begin")
    
    def _cancel_conversion_job(self, job: ConversionJob):
        """Cancel a conversion job."""
        if self.conversion_queue.cancel_job(job):
            # Update display
            self.conversion_queue_view.update_job(job)
        else:
            print('ERROR: Failed to cancel conversion job')
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to cancel conversion job")
    
    def _remove_conversion_job_from_queue(self, job: ConversionJob):
        """Remove a conversion job from the conversion queue."""
        # Check if job is currently being processed
        if self.conversion_queue.is_job_processing(job):
            print(f"[DEBUG] Conversion job {job.title} is currently being processed, will be cancelled")
        
        # Remove the job from the queue
        if self.conversion_queue.remove_job(job):
            print(f"[DEBUG] Successfully removed/cancelled conversion job: {job.title}")
        else:
            print(f"[DEBUG] Failed to remove conversion job from queue: {job.title}")
    
    def _start_conversions(self):
        print(f"[DEBUG] _start_conversions called. conversions_running: {self.conversions_running}")
        if not self.conversions_running:
            self.conversions_running = True
            print("[DEBUG] Starting/resuming conversion queue")
            self.conversion_queue_view.start_button.configure(state="disabled")
            self.conversion_queue.start()  # This will start or resume the queue
        else:
            print("[DEBUG] Conversions already running, ignoring start request")
    
    def _convert_job(self, job: ConversionJob):
        """Convert a job using the file converter."""
        try:
            print(f"Starting conversion for job: {job.title}")
            
            # Update job status
            job.status = ConversionStatus.CONVERTING
            
            # Create progress callback
            def conversion_progress(progress: float):
                # Update job progress
                job.progress = progress
                # Update UI in main thread
                self.root.after(0, lambda: self.conversion_queue_view.update_job(job))
            
            # Extract custom filename if job has output_path set
            custom_filename = None
            if job.output_path:
                custom_filename = os.path.basename(job.output_path)
                # Remove extension if present to let converter add the correct one
                custom_filename = os.path.splitext(custom_filename)[0]
            
            # Start conversion with custom filename
            output_path = self.file_converter.convert_file(
                job.input_path, job.target_format, job.output_folder, 
                conversion_progress, custom_filename
            )
            
            # Set output path and mark as completed
            job.output_path = output_path
            job.status = ConversionStatus.COMPLETED
            job.progress = 100.0
            print(f"Conversion completed for job: {job.title}")
            
        except Exception as e:
            print(f"Conversion failed for job {job.title}: {e}")
            job.status = ConversionStatus.FAILED
            job.error_message = safe_error_message(e)
        finally:
            # Check if queue is empty and pause if so
            if self.conversion_queue.get_queue_size() == 0:
                print("[DEBUG] Conversion queue empty, pausing conversions")
                self.conversions_running = False
                self.conversion_queue.pause()  # Pause the queue instead of stopping
                self.conversion_queue_view.start_button.configure(state="normal")
    
    def _convert_file(self, input_path: str, target_format: str, output_folder: str):
        """
        Convert a file to the specified format with maximum compatibility.
        
        Args:
            input_path: Path to the input file
            target_format: Target format ('mp4' or 'mp3')
            output_folder: Output folder path
        """
        def conversion_progress(progress: float):
            """Update conversion progress in the UI."""
            # This could be enhanced to show progress in the UI
            print(f"[DEBUG] Conversion progress: {progress:.1f}%")
        
        try:
            # Run conversion in a separate thread to avoid blocking the UI
            def run_conversion():
                try:
                    output_path = self.file_converter.convert_file(
                        input_path, target_format, output_folder, conversion_progress
                    )
                    
                    # Show success message in main thread
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Conversion Complete",
                        f"File successfully converted to {target_format.upper()}!\n\nOutput: {os.path.basename(output_path)}"
                    ))
                    
                except Exception as e:
                    # Show error message in main thread
                    self.root.after(0, lambda: messagebox.showerror(
                        "Conversion Failed",
                        f"Failed to convert file: {safe_error_message(e)}"
                    ))
            
            # Start conversion thread
            conversion_thread = threading.Thread(target=run_conversion, daemon=True)
            conversion_thread.start()
            
        except Exception as e:
            messagebox.showerror(
                "Conversion Error",
                f"Failed to start conversion: {safe_error_message(e)}"
            )
    
    def _setup_ui_updates(self):
        """Setup periodic UI updates with adaptive frequency."""
        def update_ui():
            # Update download queue view for all jobs
            active_jobs = [job for job in self.download_queue_view.jobs if job.status == JobStatus.DOWNLOADING]
            
            # Adaptive update frequency: faster when downloading, slower when idle
            if active_jobs:
                # Active downloads: update every 100ms
                update_interval = 100
                # Update all jobs
                for job in self.download_queue_view.jobs:
                    self.download_queue_view.update_job(job)
            else:
                # Idle: update every 500ms
                update_interval = 500
                # Update jobs that might have changed (including completed ones)
                for job in self.download_queue_view.jobs:
                    if job.status in [JobStatus.PENDING, JobStatus.COMPLETED, JobStatus.FAILED]:
                        self.download_queue_view.update_job(job)
            
            # Update conversion queue view
            active_conversions = [job for job in self.conversion_queue_view.jobs if job.status == ConversionStatus.CONVERTING]
            if active_conversions:
                # Active conversions: update all jobs
                for job in self.conversion_queue_view.jobs:
                    self.conversion_queue_view.update_job(job)
            else:
                # Idle: update jobs that might have changed (including completed ones)
                for job in self.conversion_queue_view.jobs:
                    if job.status in [ConversionStatus.PENDING, ConversionStatus.COMPLETED, ConversionStatus.FAILED]:
                        self.conversion_queue_view.update_job(job)
            
            # Periodically clean up completed jobs (every 10 seconds)
            self._cleanup_counter += 1
            
            if self._cleanup_counter >= 100:  # 100 * 100ms = 10 seconds
                # Note: cleanup_completed_jobs was removed - jobs are now manually cleared
                self._cleanup_counter = 0
            
            # Schedule next update with adaptive interval
            self.root.after(update_interval, update_ui)
        
        # Start UI updates
        self.root.after(100, update_ui)
    
    def _add_job_to_queue(self, job: DownloadJob):
        """Add a job to the download queue."""
        print(f"Adding job to queue: {job.url} - {job.title}")
        
        # Check if queue is full
        if self.download_queue.is_queue_full():
            print('ERROR: Download queue full')
            traceback.print_exc()
            messagebox.showerror("Queue Full", f"Download queue is full (maximum {self.download_queue.get_queue_capacity()} jobs). Please wait for some downloads to complete.")
            return
        
        # Add to download queue view
        self.download_queue_view.add_job(job)
        
        # Add to download queue
        if not self.download_queue.add_job(job):
            print('ERROR: Failed to add job to queue')
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to add job to queue")
            return
        
        # Defensive: Always pause the queue after adding a job
        self.download_queue.pause()
        
        print(f"Job added successfully. Queue size: {self.download_queue.get_queue_size()}")
        
        # Check if downloads are currently running
        if not self.downloads_running:
            print("[DEBUG] Downloads not running - user must click 'Start Downloads' to begin")
        
        # Update configuration and sidebar with the new output folder
        self.config["output_folder"] = job.output_folder
        self.sidebar.set_output_folder(job.output_folder)
        self._save_config()
        
        # Jobs will only start when user clicks "Start Downloads" button
        # The download queue is paused until explicitly resumed
    
    def _cancel_job(self, job: DownloadJob):
        """Cancel a download job."""
        if self.download_queue.cancel_job(job):
            # Update display
            self.download_queue_view.update_job(job)
        else:
            print('ERROR: Failed to cancel job')
            traceback.print_exc()
            messagebox.showerror("Error", "Failed to cancel job")
    
    def _remove_job_from_queue(self, job: DownloadJob):
        """Remove a job from the download queue."""
        # Check if job is currently being processed
        if self.download_queue.is_job_processing(job):
            print(f"[DEBUG] Job {job.url} is currently being processed, will be cancelled")
        
        # Remove the job from the queue
        if self.download_queue.remove_job(job):
            print(f"[DEBUG] Successfully removed/cancelled job: {job.url}")
        else:
            print(f"[DEBUG] Failed to remove job from download queue: {job.url}")
    
    def _start_downloads(self):
        print(f"[DEBUG] _start_downloads called. downloads_running: {self.downloads_running}")
        if not self.downloads_running:
            self.downloads_running = True
            print("[DEBUG] Starting/resuming download queue")
            self.download_queue_view.start_button.configure(state="disabled")
            self.download_queue.start()  # This will start or resume the queue
        else:
            print("[DEBUG] Downloads already running, ignoring start request")
    
    def _download_job(self, job: DownloadJob):
        """Download a job using the downloader."""
        try:
            print(f"Starting download for job: {job.url}")
            
            # Update job status
            job.status = JobStatus.DOWNLOADING
            
            # Create progress callback
            def progress_callback(updated_job):
                # This will be called from the downloader thread
                # We'll update the UI in the main thread
                print(f"Progress update: {updated_job.progress:.1f}% - {updated_job.speed or 'N/A'}")
            
            # Start download
            self.downloader.download_with_retry(job, progress_callback)
            
            # Set status to completed if download succeeded
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            print(f"Download completed for job: {job.url}")
            
        except Exception as e:
            print(f"Download failed for job {job.url}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = safe_error_message(e)
        finally:
            # Check if queue is empty and pause if so
            if self.download_queue.get_queue_size() == 0:
                print("[DEBUG] Queue empty, pausing downloads")
                self.downloads_running = False
                self.download_queue.pause()  # Pause the queue instead of stopping
                self.download_queue_view.start_button.configure(state="normal")
    
    def _on_closing(self):
        """Handle application closing."""
        # Stop download queue
        self.download_queue.stop()
        
        # Stop conversion queue
        self.conversion_queue.stop()
        
        # Clean up subprocesses
        self.downloader.cleanup_subprocesses()
        
        # Save configuration
        self._save_config()
        
        # Close window
        self.root.destroy()
    
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    try:
        app = BigGayDownloader()
        app.run()
    except Exception as e:
        import traceback
        print('ERROR: Exception in main loop')
        traceback.print_exc()
        import sys
        sys.stderr.flush()
        messagebox.showerror("Error", safe_error_message(e))


if __name__ == "__main__":
    main() 