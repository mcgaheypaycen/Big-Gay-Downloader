"""
Sidebar UI component for YouTube Downloader application.
Contains link entry, format selection, and add-to-queue functionality.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
from typing import Callable, Optional
import os
import subprocess
import json
import sys
from pathlib import Path
import traceback
from urllib.parse import urlparse

from core.utils import (
    sanitize_url, is_valid_url, get_playlist_videos, 
    probe_playlist, validate_output_permissions, 
    check_system_resources, safe_error_message, _find_yt_dlp,
    is_adult_content_site
)
from core.queue import DownloadJob

# CustomTkinter Switch (replaces ToggleSwitch)
class ModernSwitch(ctk.CTkSwitch):
    """
    Modern switch widget with high-tech styling.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            progress_color="#00d4ff",  # Cyan for high-tech feel
            button_color="#1f2937",
            button_hover_color="#374151",
            border_color="#4b5563",
            fg_color="#111827"
        )

class DebugDialog:
    """Dialog for showing detailed debug information."""
    
    def __init__(self, parent, title, error_details, yt_dlp_output=None, yt_dlp_command=None):
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(f"Debug Info - {title}")
        self.dialog.geometry("600x500")
        self.dialog.resizable(True, True)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (500 // 2)
        self.dialog.geometry(f"600x500+{x}+{y}")
        
        # Create main frame
        main_frame = ctk.CTkFrame(self.dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text=f"Error Details: {title}", font=("Arial", 12, "bold"))
        title_label.pack(anchor="w", pady=(0, 10))
        
        # Error Details
        error_frame = ctk.CTkFrame(main_frame)
        error_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        error_text = scrolledtext.ScrolledText(error_frame, wrap="word", height=15)
        error_text.pack(fill="both", expand=True, padx=5, pady=5)
        error_text.insert("1.0", error_details)
        error_text.config(state="disabled")
        
        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        copy_button = ctk.CTkButton(button_frame, text="Copy All to Clipboard", command=self._copy_to_clipboard)
        copy_button.pack(side="left", padx=(0, 10))
        
        close_button = ctk.CTkButton(button_frame, text="Close", command=self.dialog.destroy)
        close_button.pack(side="right")
        
        # Store data for copying
        self.error_details = error_details
        self.yt_dlp_output = yt_dlp_output
        self.yt_dlp_command = yt_dlp_command
    
    def _copy_to_clipboard(self):
        """Copy all debug information to clipboard."""
        clipboard_text = f"Error Details:\n{self.error_details}\n\n"
        
        if self.yt_dlp_command:
            clipboard_text += f"yt-dlp Command:\n{' '.join(self.yt_dlp_command)}\n\n"
        
        if self.yt_dlp_output:
            clipboard_text += f"yt-dlp Output:\n{self.yt_dlp_output}\n"
        
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(clipboard_text)
        
        # Show confirmation
        messagebox.showinfo("Copied", "Debug information copied to clipboard!")

def detect_platform(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if any(domain in netloc for domain in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif "xvideos.com" in netloc:
        return "xvideos"
    else:
        return "unknown"

class SidebarFrame(ctk.CTkFrame):
    """
    Sidebar frame containing input controls and format selection.
    """
    
    def __init__(self, parent, add_job_callback: Callable[[DownloadJob], None], 
                 output_folder: str = "", folder_change_callback: Optional[Callable[[str], None]] = None,
                 add_conversion_job_callback: Optional[Callable[[str, str, str], None]] = None):
        try:
            super().__init__(parent, width=320)  # Increased width for better proportions
            self.add_job_callback = add_job_callback
            self.folder_change_callback = folder_change_callback
            self.add_conversion_job_callback = add_conversion_job_callback
            self.update_callback = None
            self.output_folder = output_folder or os.path.expanduser("~/Downloads")
            self.selected_file_path = ""
            self.current_mode = "youtube"  # Default to YouTube mode
            try:
                self._create_widgets()
            except Exception as e:
                print('ERROR: Exception in SidebarFrame._create_widgets')
                traceback.print_exc()
                raise
            try:
                self._layout_widgets()
            except Exception as e:
                print('ERROR: Exception in SidebarFrame._layout_widgets')
                traceback.print_exc()
                raise
        except Exception as e:
            print('ERROR: Exception in SidebarFrame.__init__')
            traceback.print_exc()
            raise
    
    def _add_to_queue(self, format_type):
        print(f"DEBUG: _add_to_queue called with format_type={format_type}")
        url = self.url_entry.get().strip()
        output_folder = self.folder_var.get()
        if not url or not output_folder:
            self._show_status("Please enter a valid URL and select an output folder", error=True)
            return
        platform = detect_platform(url)
        if platform not in ("youtube", "xvideos"):
            self._show_status("Invalid YouTube or XVideos URL", error=True)
            return
        if not is_valid_url(url, platform):
            self._show_status("Invalid YouTube or XVideos URL", error=True)
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
            
            count, playlist_title, error_details, yt_dlp_output = probe_playlist(url, platform)
            
            if count == 0:
                # Show debug dialog with detailed error information
                yt_dlp_command = [_find_yt_dlp(), '--quiet', '--flat-playlist', '--dump-single-json', url]
                
                debug_dialog = DebugDialog(
                    self,
                    "Could not access URL",
                    f"URL: {url}\nPlatform: {platform}\n\nError: {error_details or 'Unknown error'}",
                    yt_dlp_output,
                    yt_dlp_command
                )
                
                self._show_status("Could not access URL - Check debug dialog", error=True)
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
            videos, video_error, video_output = get_playlist_videos(url, platform)
            
            if not videos:
                # Show debug dialog with detailed error information
                yt_dlp_command = [_find_yt_dlp(), '--quiet', '--flat-playlist', '--dump-single-json', url]
                
                debug_dialog = DebugDialog(
                    self,
                    "Could not get video information",
                    f"URL: {url}\nPlatform: {platform}\n\nError: {video_error or 'Unknown error'}",
                    video_output,
                    yt_dlp_command
                )
                
                self._show_status("Could not get video information - Check debug dialog", error=True)
                return
            
            # Limit to requested count (for "No" option on large playlists)
            if count == 1:
                videos = videos[:1]
            
            # Create and add job(s) for each individual video
            for video in videos:
                # Use the individual video URL from the playlist
                # The get_playlist_videos function already handles CDN URL issues
                job = DownloadJob(
                    url=video['url'],  # Use individual video URL from playlist
                    format=format_type,
                    output_folder=output_folder,
                    mode=platform,
                    compatibility_mode=bool(self.compatibility_toggle.get()),
                    title=video['title']
                )
                self.add_job_callback(job)
            
            # Show status message
            if len(videos) == 1:
                self._show_status("Added to queue")
            else:
                self._show_status(f"Added {len(videos)} videos to queue")
            
            self.url_entry.delete(0, "end")
                
        except Exception as e:
            # Show debug dialog for unexpected exceptions
            error_details = f"Unexpected error: {safe_error_message(e)}\n\nFull error: {str(e)}"
            debug_dialog = DebugDialog(
                self,
                "Unexpected Error",
                error_details,
                None,
                None
            )
            self._show_status(safe_error_message(e), error=True)
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Mode Toggle Section
        # self.mode_frame = ctk.CTkFrame(self)
        # self.mode_label = ctk.CTkLabel(self.mode_frame, text="Mode:", font=("Arial", 12, "bold"))
        # self.youtube_label = ctk.CTkLabel(self.mode_frame, text="YouTube", text_color="#a8a8a8", font=("Segoe UI", 11))
        # self.mode_toggle = ModernSwitch(self.mode_frame, text=None)
        # self.mode_toggle.configure(command=self._on_mode_toggle)
        # self.xvideos_label = ctk.CTkLabel(self.mode_frame, text="XVideos", text_color="#a8a8a8", font=("Segoe UI", 11))
        
        # URL Label and Entry (will be updated based on mode)
        self.url_label = ctk.CTkLabel(self, text="Video URL:", font=("Arial", 12, "bold"))
        self.url_entry = ctk.CTkEntry(self, width=40, font=("Segoe UI", 11))
        self.url_entry.bind('<Return>', lambda event: self._add_to_queue('mp4'))

        # MP4 and MP3 Buttons
        self.add_mp4_button = ctk.CTkButton(self, text="Add Video", command=lambda: self._add_to_queue('mp4'), font=("Segoe UI", 11))
        self.add_mp3_button = ctk.CTkButton(self, text="Add Audio", command=lambda: self._add_to_queue('mp3'), font=("Segoe UI", 11))
        
        # Compatibility Mode Toggle Switch (in a horizontal frame)
        self.compatibility_row = ctk.CTkFrame(self)
        self.compatibility_label = ctk.CTkLabel(self.compatibility_row, text="Compatibility Mode:", font=("Segoe UI", 11))
        self.compatibility_toggle = ModernSwitch(self.compatibility_row, text=None)
        self.compatibility_toggle.configure(command=self._on_compatibility_toggle)
        
        # Update yt-dlp button
        self.update_button = ctk.CTkButton(self, text="Update yt-dlp", command=self._update_yt_dlp, font=("Segoe UI", 11))
        
        # Separator
        self.separator1 = ctk.CTkFrame(self, height=2)
        self.separator1.configure(fg_color="#2a2b36")
        
        # File Conversion Section
        self.convert_label = ctk.CTkLabel(self, text="Convert Files:", font=("Arial", 12, "bold"))
        self.file_path_var = ctk.StringVar(value="No file selected")
        self.file_path_entry = ctk.CTkEntry(self, textvariable=self.file_path_var, width=35, state='readonly', font=("Segoe UI", 11))
        self.select_file_button = ctk.CTkButton(self, text="Browse Files", command=self._select_file, font=("Segoe UI", 11))
        self.convert_mp4_button = ctk.CTkButton(self, text="Convert to Video", command=lambda: self._add_conversion_job('mp4'), font=("Segoe UI", 11))
        self.convert_mp3_button = ctk.CTkButton(self, text="Convert to Audio", command=lambda: self._add_conversion_job('mp3'), font=("Segoe UI", 11))
        
        # Separator
        self.separator2 = ctk.CTkFrame(self, height=2)
        self.separator2.configure(fg_color="#2a2b36")

        # Output Folder Label, Entry, and Browse Button
        self.folder_label = ctk.CTkLabel(self, text="Output Folder:", font=("Arial", 12, "bold"))
        self.folder_var = ctk.StringVar(value=self.output_folder)
        self.folder_entry = ctk.CTkEntry(self, textvariable=self.folder_var, width=35, font=("Segoe UI", 11))
        self.folder_entry.bind('<FocusOut>', self._on_folder_entry_change)
        self.folder_button = ctk.CTkButton(self, text="Browse Folder", command=self._browse_folder, font=("Segoe UI", 11))

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="", text_color="#a8a8a8", font=("Segoe UI", 10))
        self.conversion_status_label = ctk.CTkLabel(self, text="", text_color="#a8a8a8", font=("Segoe UI", 10))
    
    def _layout_widgets(self):
        """Layout all widgets in the frame."""
        # Mode toggle section (at the very top)
        # self.mode_frame.pack(anchor="w", padx=16, pady=(16, 8))
        # self.mode_label.pack(side="left")
        # self.youtube_label.pack(side="left", padx=(12, 6))
        # self.mode_toggle.pack(side="left", padx=(6, 6))
        # self.xvideos_label.pack(side="left")
        
        # Output folder section
        self.folder_label.pack(anchor="w", padx=16, pady=(16, 6))
        self.folder_entry.pack(fill="x", padx=16, pady=(0, 6))
        self.folder_button.pack(fill="x", padx=16, pady=(0, 16))
        
        # Separator
        self.separator1.pack(fill="x", padx=16, pady=12)
        
        # URL section (now below output folder)
        self.url_label.pack(anchor="w", padx=16, pady=(12, 6))
        self.url_entry.pack(fill="x", padx=16, pady=(0, 8))
        self.add_mp4_button.pack(fill="x", padx=16, pady=(0, 6))
        self.add_mp3_button.pack(fill="x", padx=16, pady=(0, 12))
        
        # Compatibility Mode row (label left, toggle right)
        self.compatibility_row.pack(anchor="w", padx=16, pady=(0, 16))
        self.compatibility_label.pack(side="left")
        self.compatibility_toggle.pack(side="left", padx=(12, 0))
        
        # Separator
        self.separator2.pack(fill="x", padx=16, pady=12)
        
        # File conversion section (now at the bottom)
        self.convert_label.pack(anchor="w", padx=16, pady=(12, 6))
        self.file_path_entry.pack(fill="x", padx=16, pady=(0, 6))
        self.select_file_button.pack(fill="x", padx=16, pady=(0, 6))
        self.convert_mp4_button.pack(fill="x", padx=16, pady=(0, 6))
        self.convert_mp3_button.pack(fill="x", padx=16, pady=(0, 12))
        self.conversion_status_label.pack(anchor="w", padx=16, pady=(0, 8))
        
        self.status_label.pack(anchor="w", padx=16, pady=(0, 16))
        
        # Update button at the bottom
        self.update_button.pack(fill="x", padx=16, pady=(24, 16))
        
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
            print('ERROR: Conversion Error - You cannot convert an audio file to a video file.')
            traceback.print_exc()
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
        """Show conversion status message with appropriate styling."""
        if error:
            self.conversion_status_label.configure(text=message, text_color="#f87171")  # Soft red for errors
        else:
            self.conversion_status_label.configure(text=message, text_color="#4ade80")  # Soft green for success
        # Clear after 5 seconds
        self.after(5000, lambda: self.conversion_status_label.configure(text="", text_color="#a8a8a8"))
    
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
        """Show status message with appropriate styling."""
        if error:
            self.status_label.configure(text=message, text_color="#f87171")  # Soft red for errors
        else:
            self.status_label.configure(text=message, text_color="#4ade80")  # Soft green for success
        # Clear after 5 seconds
        self.after(5000, lambda: self.status_label.configure(text="", text_color="#a8a8a8"))
    
    def set_output_folder(self, folder: str):
        """Set the output folder and update the entry."""
        self.output_folder = folder
        self.folder_var.set(folder)
    
    def get_output_folder(self) -> str:
        """Get the current output folder."""
        return self.output_folder
    
    def _on_mode_toggle(self, value):
        """Handle mode toggle between YouTube and XVideos."""
        if value:
            self.current_mode = "xvideos"
            self.url_label.config(text="XVideos URL:")
        else:
            self.current_mode = "youtube"
            self.url_label.config(text="YouTube URL:")
        
        # Clear the URL entry when switching modes
        self.url_entry.delete(0, "end")
        
        # Show a brief status message
        self._show_status(f"Switched to {self.current_mode.capitalize()} mode") 