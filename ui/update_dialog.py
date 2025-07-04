"""
Update dialog for YouTube Downloader application.
Provides a modal dialog for yt-dlp updates with progress tracking.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable
import threading

from core.yt_dlp_installer import InstallerStatus
from core.version_manager import VersionManager, UpdatePriority


class UpdateDialog(tk.Toplevel):
    """
    Modal dialog for yt-dlp updates.
    """
    
    def __init__(self, parent, 
                 current_version: str,
                 latest_version: str,
                 update_callback: Callable[[Callable[[InstallerStatus, float, str], None], Callable[[bool, str], None]], None],
                 release_notes: str = ""):
        """
        Initialize the update dialog.
        
        Args:
            parent: Parent window
            current_version: Current yt-dlp version
            latest_version: Latest available version
            update_callback: Callback to start the update process
            release_notes: Release notes for the update
        """
        super().__init__(parent)
        
        self.current_version = current_version
        self.latest_version = latest_version
        self.update_callback = update_callback
        self.release_notes = release_notes
        
        # Dialog setup
        self.title("Update yt-dlp")
        self.geometry("500x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog
        self.center_on_parent(parent)
        
        # State variables
        self.is_updating = False
        self.update_thread = None
        
        # Create UI
        self._create_widgets()
        self._layout_widgets()
        
        # Focus on the dialog
        self.focus_set()
        self.wait_window()
    
    def center_on_parent(self, parent):
        """Center the dialog on its parent window."""
        self.update_idletasks()
        
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 500
        dialog_height = 400
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self, padding="20")
        
        # Title
        self.title_label = ttk.Label(
            self.main_frame, 
            text="Update yt-dlp",
            font=("Arial", 16, "bold")
        )
        
        # Version information
        self.version_frame = ttk.LabelFrame(self.main_frame, text="Version Information", padding="10")
        
        self.current_version_label = ttk.Label(
            self.version_frame,
            text=f"Current Version: {VersionManager.format_version_display(self.current_version)}"
        )
        
        self.latest_version_label = ttk.Label(
            self.version_frame,
            text=f"Latest Version: {VersionManager.format_version_display(self.latest_version)}"
        )
        
        # Update description
        self.description_label = ttk.Label(
            self.main_frame,
            text=VersionManager.get_update_description(self.current_version, self.latest_version),
            wraplength=450,
            justify="left"
        )
        
        # Release notes (if available)
        if self.release_notes:
            self.notes_frame = ttk.LabelFrame(self.main_frame, text="Release Notes", padding="10")
            self.notes_text = tk.Text(
                self.notes_frame,
                height=6,
                width=60,
                wrap="word",
                state="disabled"
            )
            self.notes_scrollbar = ttk.Scrollbar(self.notes_frame, orient="vertical", command=self.notes_text.yview)
            self.notes_text.configure(yscrollcommand=self.notes_scrollbar.set)
            
            # Insert release notes
            self.notes_text.config(state="normal")
            self.notes_text.insert("1.0", self.release_notes)
            self.notes_text.config(state="disabled")
        
        # Progress frame (initially hidden)
        self.progress_frame = ttk.LabelFrame(self.main_frame, text="Update Progress", padding="10")
        
        self.progress_label = ttk.Label(self.progress_frame, text="Preparing update...")
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode="determinate",
            length=400
        )
        self.progress_percent = ttk.Label(self.progress_frame, text="0%")
        
        # Buttons
        self.button_frame = ttk.Frame(self.main_frame)
        
        self.update_button = ttk.Button(
            self.button_frame,
            text="Update Now",
            command=self._start_update,
            style="Accent.TButton"
        )
        
        self.close_button = ttk.Button(
            self.button_frame,
            text="Close",
            command=self.destroy,
            style="Sidebar.TButton"
        )
    
    def _layout_widgets(self):
        """Layout all widgets."""
        self.main_frame.pack(fill="both", expand=True)
        
        # Title
        self.title_label.pack(pady=(0, 20))
        
        # Version information
        self.version_frame.pack(fill="x", pady=(0, 15))
        self.current_version_label.pack(anchor="w")
        self.latest_version_label.pack(anchor="w")
        
        # Description
        self.description_label.pack(fill="x", pady=(0, 15))
        
        # Release notes
        if hasattr(self, 'notes_frame'):
            self.notes_frame.pack(fill="both", expand=True, pady=(0, 15))
            self.notes_text.pack(side="left", fill="both", expand=True)
            self.notes_scrollbar.pack(side="right", fill="y")
        
        # Progress frame (initially hidden)
        self.progress_frame.pack(fill="x", pady=(0, 15))
        self.progress_label.pack(anchor="w", pady=(0, 5))
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_percent.pack(anchor="w")
        self.progress_frame.pack_forget()  # Hide initially
        
        # Buttons
        self.button_frame.pack(fill="x", pady=(20, 0))
        self.update_button.pack(side="right", padx=(5, 0))
        self.close_button.pack(side="right")
        
        # Add hover effect to the 'Close' button to match sidebar
        def on_close_enter(e):
            self.close_button.configure(style="Sidebar.TButton")
        def on_close_leave(e):
            self.close_button.configure(style="Sidebar.TButton")
        self.close_button.bind("<Enter>", on_close_enter)
        self.close_button.bind("<Leave>", on_close_leave)
    
    def _start_update(self):
        """Start the update process."""
        if self.is_updating:
            return
        
        # Confirm update
        priority = VersionManager.determine_update_priority(self.current_version, self.latest_version)
        
        if priority in [UpdatePriority.HIGH, UpdatePriority.CRITICAL]:
            message = f"This is a {priority.value} priority update. Continue?"
        else:
            message = "Start the update process?"
        
        if not messagebox.askyesno("Confirm Update", message):
            return
        
        # Show progress frame
        self.progress_frame.pack(fill="x", pady=(0, 15))
        
        # Hide buttons except cancel
        self.update_button.pack_forget()
        self.close_button.pack_forget()
        
        # Start update
        self.is_updating = True
        self.update_callback(
            self._progress_callback,
            self._completion_callback
        )
    
    def _progress_callback(self, status: InstallerStatus, progress: float, message: str):
        """Handle progress updates from the installer."""
        if not self.is_updating:
            return
        
        # Update UI in main thread
        self.after(0, self._update_progress, status, progress, message)
    
    def _update_progress(self, status: InstallerStatus, progress: float, message: str):
        """Update progress display (called in main thread)."""
        if not self.is_updating:
            return
        
        # Update progress bar
        self.progress_bar["value"] = progress
        self.progress_percent["text"] = f"{progress:.1f}%"
        
        # Update status message
        status_text = f"{status.value.title()}: {message}"
        self.progress_label["text"] = status_text
        
        # Update window title
        self.title(f"Update yt-dlp - {progress:.1f}%")
    
    def _completion_callback(self, success: bool, message: str):
        """Handle completion of the update process."""
        self.is_updating = False
        
        # Update UI in main thread
        self.after(0, self._handle_completion, success, message)
    
    def _handle_completion(self, success: bool, message: str):
        """Handle completion (called in main thread)."""
        if success:
            # Show success message
            messagebox.showinfo("Update Complete", f"yt-dlp has been updated successfully!\n\n{message}")
            
            # Update version display
            self.current_version_label["text"] = f"Current Version: {VersionManager.format_version_display(self.latest_version)}"
            self.description_label["text"] = "yt-dlp is up to date."
            
            # Show close button
            self.close_button.pack(side="right")
            
            # Hide progress frame
            self.progress_frame.pack_forget()
            
        else:
            # Show error message
            messagebox.showerror("Update Failed", f"Failed to update yt-dlp:\n\n{message}")
            
            # Restore buttons
            self.update_button.pack(side="right", padx=(5, 0))
            self.close_button.pack(side="right")
            
            # Hide progress frame
            self.progress_frame.pack_forget()


class UpdateNotificationDialog(tk.Toplevel):
    """
    Simple notification dialog for available updates.
    """
    
    def __init__(self, parent, 
                 current_version: str,
                 latest_version: str,
                 update_callback: Callable[[Callable[[InstallerStatus, float, str], None], Callable[[bool, str], None]], None]):
        """
        Initialize the update notification dialog.
        
        Args:
            parent: Parent window
            current_version: Current yt-dlp version
            latest_version: Latest available version
            update_callback: Callback to start the update process
        """
        super().__init__(parent)
        
        self.current_version = current_version
        self.latest_version = latest_version
        self.update_callback = update_callback
        
        # Dialog setup
        self.title("Update")
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog
        self.center_on_parent(parent)
        
        # Create UI
        self._create_widgets()
        self._layout_widgets()
        
        # Focus on the dialog
        self.focus_set()
        self.wait_window()
    
    def center_on_parent(self, parent):
        """Center the dialog on its parent window."""
        self.update_idletasks()
        
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 400
        dialog_height = 200
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main frame
        self.main_frame = ttk.Frame(self, padding="20")
        
        # Icon and title
        self.title_label = ttk.Label(
            self.main_frame,
            text="🔄 Update Available",
            font=("Arial", 14, "bold")
        )
        
        # Message
        self.message_label = ttk.Label(
            self.main_frame,
            text=f"A new version of yt-dlp is available:\n{self.current_version} → {self.latest_version}",
            wraplength=350,
            justify="center"
        )
        
        # Buttons
        self.button_frame = ttk.Frame(self.main_frame)
        
        self.update_button = ttk.Button(
            self.button_frame,
            text="Update Now",
            command=self._open_update_dialog,
            style="Accent.TButton"
        )
        
        self.later_button = ttk.Button(
            self.button_frame,
            text="Later",
            command=self.destroy,
            style="Sidebar.TButton"
        )
    
    def _layout_widgets(self):
        """Layout all widgets."""
        self.main_frame.pack(fill="both", expand=True)
        
        # Title
        self.title_label.pack(pady=(0, 15))
        
        # Message
        self.message_label.pack(fill="x", pady=(0, 20))
        
        # Buttons
        self.button_frame.pack(fill="x")
        self.update_button.pack(side="right", padx=(5, 0))
        self.later_button.pack(side="right")
        
        # Add hover effect to the 'Later' button to match sidebar
        def on_later_enter(e):
            self.later_button.configure(style="Sidebar.TButton")
        def on_later_leave(e):
            self.later_button.configure(style="Sidebar.TButton")
        self.later_button.bind("<Enter>", on_later_enter)
        self.later_button.bind("<Leave>", on_later_leave)
    
    def _open_update_dialog(self):
        """Open the full update dialog."""
        self.destroy()
        UpdateDialog(
            self.master,
            self.current_version,
            self.latest_version,
            self.update_callback
        ) 