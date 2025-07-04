"""
Sidebar UI component for YouTube Downloader application.
Contains link entry, format selection, and add-to-queue functionality.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional
import os
import subprocess
import json

from core.utils import is_valid_url, probe_playlist, get_playlist_videos, validate_output_permissions, safe_error_message, check_system_resources
from core.queue import DownloadJob

# Restore ToggleSwitch class
class ToggleSwitch(tk.Canvas):
    """
    Custom toggle switch widget.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.state = tk.BooleanVar(value=False)
        self.callback = None
        self.width = 50
        self.height = 24
        self.configure(width=self.width, height=self.height, bg='#1B1F24', highlightthickness=0)
        self._draw_switch()
        self.bind('<Button-1>', self._toggle)
    def _draw_switch(self):
        self.delete("all")
        bg_color = '#7873F5' if self.state.get() else '#2D3748'
        self.create_rounded_rectangle(2, 2, self.width-2, self.height-2, fill=bg_color, outline='#4A5568', width=1)
        circle_x = self.width - 12 if self.state.get() else 12
        self.create_oval(circle_x-8, 4, circle_x+8, self.height-4, fill='white', outline='#E2E8F0', width=1)
    def create_rounded_rectangle(self, x1, y1, x2, y2, **kwargs):
        radius = 10
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    def _toggle(self, event=None):
        self.state.set(not self.state.get())
        self._draw_switch()
        if self.callback:
            self.callback(self.state.get())
    def get(self):
        return self.state.get()
    def set(self, value):
        self.state.set(value)
        self._draw_switch()
    def set_callback(self, callback):
        self.callback = callback

class SidebarFrame(ttk.Frame):
    """
    Sidebar frame containing input controls and format selection.
    """
    
    def __init__(self, parent, add_job_callback: Callable[[DownloadJob], None], 
                 output_folder: str = "", folder_change_callback: Optional[Callable[[str], None]] = None,
                 add_conversion_job_callback: Optional[Callable[[str, str, str], None]] = None):
        """
        Initialize the sidebar frame.
        
        Args:
            parent: Parent widget
            add_job_callback: Callback function to add a job to the queue
            output_folder: Default output folder path
            folder_change_callback: Optional callback when output folder changes
            add_conversion_job_callback: Optional callback for adding conversion jobs to queue
        """
        super().__init__(parent)
        self.config(width=240)
        self.add_job_callback = add_job_callback
        self.folder_change_callback = folder_change_callback
        self.add_conversion_job_callback = add_conversion_job_callback
        self.update_callback = None
        self.output_folder = output_folder or os.path.expanduser("~/Downloads")
        self.selected_file_path = ""
        self.config(borderwidth=2, relief="solid", height=600)
        self.pack_propagate(False)
        self._create_widgets()
        self._layout_widgets()
    
    def _add_to_queue(self, format_type):
        print(f"DEBUG: _add_to_queue called with format_type={format_type}")
        url = self.url_entry.get().strip()
        output_folder = self.folder_var.get()
        if not url or not output_folder:
            self._show_status("Please enter a valid URL and select an output folder", error=True)
            return
        
        if not is_valid_url(url):
            self._show_status("Invalid URL", error=True)
            return
        
        if not os.path.exists(output_folder):
            self._show_status("Output folder does not exist", error=True)
            return
        
        if not validate_output_permissions(output_folder):
            self._show_status("Output folder is not writable", error=True)
            return
        
        # Check system resources
        resource_status = check_system_resources(output_folder)
        if not all([resource_status['disk_space_ok'], resource_status['memory_ok'], resource_status['network_ok']]):
            error_msg = "System resource issues detected: " + "; ".join(resource_status['errors'])
            self._show_status(error_msg, error=True)
            return
        
        # Probe for playlist
        try:
            self._show_status("Checking URL...")
            self.update_idletasks()
            
            count, playlist_title = probe_playlist(url)
            
            if count == 0:
                self._show_status("Could not access URL", error=True)
                return
            
            # Ask for confirmation if it's a large playlist
            if count > 1:
                message = f"Playlist detected: {count} videos\nTitle: {playlist_title}\n\nDownload all videos?"
                result = messagebox.askyesnocancel(
                    "Playlist Confirmation",
                    message,
                    icon=messagebox.QUESTION
                )
                
                if result is None:  # Cancel
                    self._show_status("Cancelled")
                    return
                elif not result:  # No - download only first video
                    count = 1
            
            # Get individual video information
            videos = get_playlist_videos(url)
            
            if not videos:
                self._show_status("Could not get video information", error=True)
                return
            
            # Limit to requested count (for "No" option on large playlists)
            if count == 1:
                videos = videos[:1]
            
            # Create and add job(s) for each individual video
            for video in videos:
                job = DownloadJob(
                    url=video['url'],
                    format=format_type,
                    output_folder=output_folder,
                    compatibility_mode=self.compatibility_toggle.get(),
                    title=video['title']
                )
                self.add_job_callback(job)
            
            # Show status message
            if len(videos) == 1:
                self._show_status("Added to queue")
            else:
                self._show_status(f"Added {len(videos)} videos to queue")
            
            self.url_entry.delete(0, tk.END)
                
        except Exception as e:
            self._show_status(safe_error_message(e), error=True)
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # YouTube URL Label and Entry
        self.url_label = ttk.Label(self, text="YouTube URL:")
        self.url_entry = ttk.Entry(self, width=40)
        self.url_entry.configure(foreground='black')
        self.url_entry.bind('<Return>', lambda event: self._add_to_queue('mp4'))

        # MP4 and MP3 Buttons
        self.add_mp4_button = ttk.Button(self, text="Add Video", command=lambda: self._add_to_queue('mp4'), style='Sidebar.TButton')
        self.add_mp4_button.config(takefocus=True)
        self.add_mp3_button = ttk.Button(self, text="Add Audio", command=lambda: self._add_to_queue('mp3'), style='Sidebar.TButton')
        self.add_mp3_button.config(takefocus=True)
        # Compatibility Mode Toggle Switch (in a horizontal frame)
        self.compatibility_row = ttk.Frame(self)
        self.compatibility_label = ttk.Label(self.compatibility_row, text="Compatibility Mode:")
        self.compatibility_toggle = ToggleSwitch(self.compatibility_row)
        
        # Update yt-dlp button
        self.update_button = ttk.Button(self, text="Update", command=self._update_yt_dlp, style='Sidebar.TButton')
        self.update_button.config(takefocus=True)
        self.compatibility_toggle.set_callback(self._on_compatibility_toggle)
        
        # Separator
        self.separator1 = ttk.Separator(self, orient='horizontal')
        
        # File Conversion Section
        self.convert_label = ttk.Label(self, text="Convert:")
        self.file_path_var = tk.StringVar(value="No file selected")
        self.file_path_entry = ttk.Entry(self, textvariable=self.file_path_var, width=35, state='readonly')
        self.file_path_entry.configure(foreground='black')
        self.select_file_button = ttk.Button(self, text="Browse", command=self._select_file, style='Sidebar.TButton')
        self.convert_mp4_button = ttk.Button(self, text="Convert Video", command=lambda: self._add_conversion_job('mp4'), style='Sidebar.TButton')
        self.convert_mp3_button = ttk.Button(self, text="Convert Audio", command=lambda: self._add_conversion_job('mp3'), style='Sidebar.TButton')
        
        # Separator
        self.separator2 = ttk.Separator(self, orient='horizontal')

        # Output Folder Label, Entry, and Browse Button
        self.folder_label = ttk.Label(self, text="Output Folder:")
        self.folder_var = tk.StringVar(value=self.output_folder)
        self.folder_entry = ttk.Entry(self, textvariable=self.folder_var, width=35)
        self.folder_entry.configure(foreground='black')
        self.folder_entry.bind('<FocusOut>', self._on_folder_entry_change)
        self.folder_button = ttk.Button(self, text="Browse", command=self._browse_folder, style='Sidebar.TButton')

        # Status Label
        self.status_label = ttk.Label(self, text="", foreground="#A1A1AA")
        self.conversion_status_label = ttk.Label(self, text="", foreground="#A1A1AA")
    
    def _layout_widgets(self):
        """Layout all widgets in the frame."""
        # Output folder section (now at the top)
        self.folder_label.pack(anchor="w", padx=10, pady=(10, 4))
        self.folder_entry.pack(fill="x", padx=10, pady=(0, 4))
        self.folder_button.pack(fill="x", padx=10, pady=(0, 12))
        
        # Separator
        self.separator1.pack(fill="x", padx=10, pady=8)
        
        # YouTube URL section (now below output folder)
        self.url_label.pack(anchor="w", padx=10, pady=(8, 4))
        self.url_entry.pack(fill="x", padx=10, pady=(0, 8))
        self.add_mp4_button.pack(fill="x", padx=10, pady=(0, 4))
        self.add_mp3_button.pack(fill="x", padx=10, pady=(0, 8))
        # Compatibility Mode row (label left, toggle right)
        self.compatibility_row.pack(anchor="w", padx=10, pady=(0, 8))
        self.compatibility_label.pack(side="left")
        self.compatibility_toggle.pack(side="left", padx=(8, 0))
        
        # Separator
        self.separator2.pack(fill="x", padx=10, pady=8)
        
        # File conversion section (now at the bottom)
        self.convert_label.pack(anchor="w", padx=10, pady=(8, 4))
        self.file_path_entry.pack(fill="x", padx=10, pady=(0, 4))
        self.select_file_button.pack(fill="x", padx=10, pady=(0, 4))
        self.convert_mp4_button.pack(fill="x", padx=10, pady=(0, 4))
        self.convert_mp3_button.pack(fill="x", padx=10, pady=(0, 8))
        self.conversion_status_label.pack(anchor="w", padx=10, pady=(0, 0))
        
        self.status_label.pack(anchor="w", padx=10, pady=(0, 0))
        
        # Update button at the bottom
        self.update_button.pack(fill="x", padx=10, pady=(20, 10))
        
        self.url_entry.focus_set()
    
    def _select_file(self):
        """Open file browser dialog to select a file for conversion."""
        file_path = filedialog.askopenfilename(
            title="Select File to Convert",
            initialdir=self.output_folder,
            filetypes=[
                ("All Supported Files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.mp3 *.m4a *.wav *.flac *.ogg *.aac"),
                ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("Audio files", "*.mp3 *.m4a *.wav *.flac *.ogg *.aac"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.selected_file_path = file_path
            # Show just the filename in the entry
            filename = os.path.basename(file_path)
            self.file_path_var.set(filename)
    
    def _add_conversion_job(self, target_format: str):
        print(f"DEBUG: _add_conversion_job called with selected_file_path={self.selected_file_path}, target_format={target_format}")
        if not self.selected_file_path:
            self._show_conversion_status("Please select a file to convert", error=True)
            return
        if not os.path.exists(self.selected_file_path):
            self._show_conversion_status("Selected file does not exist", error=True)
            return
        # Prevent converting mp3 to mp4
        if self.selected_file_path.lower().endswith('.mp3') and target_format == 'mp4':
            messagebox.showerror("Conversion Error", "You cannot convert an audio file to a video file.")
            return
        output_folder = self.folder_var.get()
        if not output_folder or not os.path.exists(output_folder):
            self._show_conversion_status("Please select a valid output folder", error=True)
            return
        if not validate_output_permissions(output_folder):
            self._show_conversion_status("Output folder is not writable", error=True)
            return
        resource_status = check_system_resources(output_folder)
        if not all([resource_status['disk_space_ok'], resource_status['memory_ok'], resource_status['network_ok']]):
            error_msg = "System resource issues detected: " + "; ".join(resource_status['errors'])
            self._show_conversion_status(error_msg, error=True)
            return
        if self.add_conversion_job_callback:
            try:
                self.add_conversion_job_callback(self.selected_file_path, target_format, output_folder)
                self._show_conversion_status('Conversion job added to queue')
                self.selected_file_path = ""
                self.file_path_var.set("No file selected")
            except Exception as e:
                self._show_conversion_status(safe_error_message(e), error=True)
        else:
            self._show_conversion_status("Conversion queue feature not available", error=True)
    
    def _show_conversion_status(self, message: str, error: bool = False):
        self.conversion_status_label.config(
            text=message,
            foreground="#EF4444" if error else "#A1A1AA"
        )
        self.after(5000, lambda: self.conversion_status_label.config(text="", foreground="#A1A1AA"))
    
    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder
        )
        if folder:
            self.output_folder = folder
            self.folder_var.set(folder)
            if self.folder_change_callback:
                self.folder_change_callback(folder)
    
    def _on_folder_entry_change(self, event):
        """Handle manual folder entry change."""
        new_folder = self.folder_var.get().strip()
        if new_folder and new_folder != self.output_folder:
            self.output_folder = new_folder
            if self.folder_change_callback:
                self.folder_change_callback(new_folder)
    
    def _on_compatibility_toggle(self, value: bool):
        pass
    
    def _update_yt_dlp(self):
        """Handle yt-dlp update button click."""
        if self.update_callback:
            self.update_callback()
        else:
            print("DEBUG: Update yt-dlp button clicked - no callback set")
            self._show_status("Update functionality not available", error=True)
    
    def set_update_callback(self, callback: Callable[[], None]):
        """Set the callback for the update button."""
        self.update_callback = callback
    
    def _show_status(self, message: str, error: bool = False):
        """Show status message."""
        self.status_label.config(
            text=message,
            foreground="#EF4444" if error else "#A1A1AA"
        )
        # Clear status after 5 seconds
        self.after(5000, lambda: self.status_label.config(text="", foreground="#A1A1AA"))
    
    def set_output_folder(self, folder: str):
        """Set the output folder."""
        self.output_folder = folder
        self.folder_var.set(folder)
    
    def get_output_folder(self) -> str:
        """Get the current output folder."""
        return self.output_folder 