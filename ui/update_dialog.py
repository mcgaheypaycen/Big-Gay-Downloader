"""
Update dialog component for YouTube Downloader application.
Handles yt-dlp updates with progress tracking.
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
import subprocess
import sys
from pathlib import Path
import traceback

from core.yt_dlp_installer import YtDlpInstaller, InstallerStatus
from core.version_manager import VersionManager


class UpdateDialog:
    """
    Dialog for updating yt-dlp with progress tracking.
    """
    
    def __init__(self, parent, current_version: str, latest_version: str):
        """
        Initialize the update dialog.
        
        Args:
            parent: Parent widget
            current_version: Current yt-dlp version
            latest_version: Latest available yt-dlp version
        """
        self.parent = parent
        self.current_version = current_version
        self.latest_version = latest_version
        self.installer = YtDlpInstaller()
        self.update_thread = None
        self.dialog = None
        
        self._create_dialog()
    
    def _create_dialog(self):
        """Create the update dialog."""
        self.dialog = ctk.CTkToplevel(self.parent)
        self.dialog.title("Update yt-dlp")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"500x400+{x}+{y}")
        
        self._create_widgets()
        self._layout_widgets()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main frame
        self.main_frame = ctk.CTkFrame(self.dialog)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame, 
            text="Update yt-dlp",
            font=("Segoe UI", 18, "bold")
        )
        
        # Version information
        self.version_frame = ctk.CTkFrame(self.main_frame)
        
        self.current_version_label = ctk.CTkLabel(
            self.version_frame,
            text=f"Current Version: {VersionManager.format_version_display(self.current_version)}",
            font=("Segoe UI", 11)
        )
        
        self.latest_version_label = ctk.CTkLabel(
            self.version_frame,
            text=f"Latest Version: {VersionManager.format_version_display(self.latest_version)}",
            font=("Segoe UI", 11)
        )
        
        # Progress section
        self.progress_frame = ctk.CTkFrame(self.main_frame)
        
        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Ready to update",
            font=("Segoe UI", 11)
        )
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.set(0)
        
        # Buttons
        self.button_frame = ctk.CTkFrame(self.main_frame)
        
        self.update_button = ctk.CTkButton(
            self.button_frame,
            text="Update Now",
            command=self._start_update,
            font=("Segoe UI", 11)
        )
        
        self.cancel_button = ctk.CTkButton(
            self.button_frame,
            text="Cancel",
            command=self._on_cancel_click,
            font=("Segoe UI", 11)
        )
    
    def _layout_widgets(self):
        """Layout all widgets."""
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        self.title_label.pack(pady=(0, 20))
        
        # Version information
        self.version_frame.pack(fill="x", pady=(0, 20))
        self.current_version_label.pack(anchor="w", padx=10, pady=5)
        self.latest_version_label.pack(anchor="w", padx=10, pady=5)
        
        # Progress section
        self.progress_frame.pack(fill="x", pady=(0, 20))
        self.progress_label.pack(anchor="w", padx=10, pady=5)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        
        # Buttons
        self.button_frame.pack(fill="x", pady=(0, 10))
        self.update_button.pack(side="left", padx=(0, 10))
        self.cancel_button.pack(side="right")
    
    def _start_update(self):
        """Start the update process."""
        if not self.dialog:
            return
            
        self.update_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        
        # Start update in background thread
        self.update_thread = threading.Thread(target=self._update_yt_dlp, daemon=True)
        self.update_thread.start()
    
    def _update_yt_dlp(self):
        """Update yt-dlp in background thread."""
        if not self.dialog:
            return
            
        try:
            # Update progress
            self.dialog.after(0, lambda: self._update_progress("Downloading yt-dlp...", 0.2))
            
            # Download and install
            result = self.installer.install_yt_dlp()
            
            if result:
                self.dialog.after(0, lambda: self._update_progress("Update completed successfully!", 1.0))
                self.dialog.after(1000, self._on_update_success)
            else:
                print('ERROR: Failed to update yt-dlp')
                traceback.print_exc()
                error_msg = "Failed to update yt-dlp"
                self.dialog.after(0, lambda: self._update_progress(error_msg, 0.0))
                self.dialog.after(1000, lambda: self._on_update_failure(error_msg))
                
        except Exception as e:
            print('ERROR: Update failed')
            traceback.print_exc()
            error_msg = f"Update failed: {str(e)}"
            self.dialog.after(0, lambda: self._update_progress(error_msg, 0.0))
            self.dialog.after(1000, lambda: self._on_update_failure(error_msg))
    
    def _update_progress(self, message: str, progress: float):
        """Update progress display."""
        if not self.dialog:
            return
        self.progress_label.configure(text=message)
        self.progress_bar.set(progress)
    
    def _on_update_success(self):
        """Handle successful update."""
        messagebox.showinfo("Update Complete", "yt-dlp has been updated successfully!")
        if self.dialog:
            self.dialog.destroy()
    
    def _on_update_failure(self, error_msg: str):
        """Handle update failure."""
        print('ERROR: Update Failed')
        traceback.print_exc()
        messagebox.showerror("Update Failed", error_msg)
        if self.dialog:
            self.update_button.configure(state="normal")
            self.cancel_button.configure(state="normal")
    
    def _on_cancel_click(self):
        """Handle cancel button click."""
        if self.dialog:
            self.dialog.destroy()


class UpdateNotificationDialog:
    """
    Simple notification dialog for available updates.
    """
    
    def __init__(self, parent, current_version: str, latest_version: str, update_callback):
        """
        Initialize the update notification dialog.
        
        Args:
            parent: Parent widget
            current_version: Current yt-dlp version
            latest_version: Latest available yt-dlp version
            update_callback: Callback function to start update
        """
        self.parent = parent
        self.current_version = current_version
        self.latest_version = latest_version
        self.update_callback = update_callback
        self.dialog = None
        
        self._create_dialog()
    
    def _create_dialog(self):
        """Create the notification dialog."""
        self.dialog = ctk.CTkToplevel(self.parent)
        self.dialog.title("Update Available")
        self.dialog.geometry("400x250")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (250 // 2)
        self.dialog.geometry(f"400x250+{x}+{y}")
        
        self._create_widgets()
        self._layout_widgets()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main frame
        self.main_frame = ctk.CTkFrame(self.dialog)
        
        # Icon and title
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="🔄 Update Available",
            font=("Segoe UI", 16, "bold")
        )
        
        # Message
        self.message_label = ctk.CTkLabel(
            self.main_frame,
            text=f"A new version of yt-dlp is available:\n{self.current_version} → {self.latest_version}",
            wraplength=350,
            justify="center",
            font=("Segoe UI", 11)
        )
        
        # Buttons
        self.button_frame = ctk.CTkFrame(self.main_frame)
        
        self.update_button = ctk.CTkButton(
            self.button_frame,
            text="Update Now",
            command=self._on_update_click,
            font=("Segoe UI", 11)
        )
        
        self.later_button = ctk.CTkButton(
            self.button_frame,
            text="Later",
            command=self._on_later_click,
            font=("Segoe UI", 11)
        )
    
    def _layout_widgets(self):
        """Layout all widgets."""
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        self.title_label.pack(pady=(0, 20))
        
        # Message
        self.message_label.pack(pady=(0, 30))
        
        # Buttons
        self.button_frame.pack(fill="x")
        self.update_button.pack(side="left", padx=(0, 10))
        self.later_button.pack(side="right")
    
    def _on_update_click(self):
        """Handle update button click."""
        if self.dialog:
            self.dialog.destroy()
        if self.update_callback:
            self.update_callback()
    
    def _on_later_click(self):
        """Handle later button click."""
        if self.dialog:
            self.dialog.destroy() 