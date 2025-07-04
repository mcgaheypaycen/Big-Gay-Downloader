"""
First launch installer for YouTube Downloader application.
Handles automatic yt-dlp installation when the app is launched for the first time.
"""

import os
import json
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from core.yt_dlp_installer import YtDlpInstaller, InstallerStatus


@dataclass
class FirstLaunchConfig:
    """Configuration for first launch behavior."""
    auto_install: bool = True
    show_install_dialog: bool = True
    skip_if_yt_dlp_exists: bool = True
    install_timeout: int = 300  # 5 minutes


class FirstLaunchManager:
    """
    Manages first launch installation of yt-dlp.
    """
    
    def __init__(self, app_data_dir: Optional[str] = None):
        """
        Initialize the first launch manager.
        
        Args:
            app_data_dir: Directory to store configuration and yt-dlp
        """
        if app_data_dir is None:
            self.app_data_dir = Path.home() / ".big_gay_yt_ripper"
        else:
            self.app_data_dir = Path(app_data_dir)
        
        self.config_file = self.app_data_dir / "first_launch_config.json"
        self.installer = YtDlpInstaller(str(self.app_data_dir))
        self.config = self._load_config()
        
        print(f"[DEBUG] FirstLaunchManager initialized with data dir: {self.app_data_dir}")
    
    def _load_config(self) -> FirstLaunchConfig:
        """Load first launch configuration."""
        default_config = FirstLaunchConfig()
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return FirstLaunchConfig(**data)
        except Exception as e:
            print(f"[DEBUG] Failed to load first launch config: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save first launch configuration."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config.__dict__, f, indent=2)
        except Exception as e:
            print(f"[DEBUG] Failed to save first launch config: {e}")
    
    def is_first_launch(self) -> bool:
        """
        Check if this is the first launch of the application.
        
        Returns:
            True if this is the first launch
        """
        # Check if the app data directory exists and has been initialized
        if not self.app_data_dir.exists():
            return True
        
        # Check if yt-dlp has been installed
        if not self.installer.is_installed():
            return True
        
        # Check if first launch flag exists
        first_launch_flag = self.app_data_dir / ".first_launch_complete"
        return not first_launch_flag.exists()
    
    def mark_first_launch_complete(self):
        """Mark that the first launch has been completed."""
        try:
            flag_file = self.app_data_dir / ".first_launch_complete"
            flag_file.touch()
            print(f"[DEBUG] Marked first launch as complete: {flag_file}")
        except Exception as e:
            print(f"[DEBUG] Failed to mark first launch complete: {e}")
    
    def should_install_yt_dlp(self) -> bool:
        """
        Determine if yt-dlp should be installed.
        
        Returns:
            True if yt-dlp should be installed
        """
        # If auto-install is disabled, don't install
        if not self.config.auto_install:
            return False
        
        # If yt-dlp already exists and we should skip, don't install
        if self.config.skip_if_yt_dlp_exists and self.installer.is_installed():
            return False
        
        # Check if this is first launch or yt-dlp is missing
        return self.is_first_launch() or not self.installer.is_installed()
    
    def install_yt_dlp_async(self, 
                           progress_callback: Optional[Callable[[InstallerStatus, float, str], None]] = None,
                           completion_callback: Optional[Callable[[bool, str], None]] = None):
        """
        Install yt-dlp asynchronously.
        
        Args:
            progress_callback: Callback for progress updates
            completion_callback: Callback when installation completes
        """
        def install_thread():
            try:
                # Create a wrapper callback to match the installer's expected signature
                def wrapper_callback(progress: float, message: str):
                    if progress_callback:
                        progress_callback(InstallerStatus.DOWNLOADING, progress, message)
                
                success = self.installer.install_yt_dlp(wrapper_callback)
                
                if success:
                    self.mark_first_launch_complete()
                    message = "yt-dlp installed successfully"
                else:
                    message = "Failed to install yt-dlp"
                
                if completion_callback:
                    completion_callback(success, message)
                    
            except Exception as e:
                print(f"[DEBUG] Installation thread error: {e}")
                if completion_callback:
                    completion_callback(False, f"Installation error: {str(e)}")
        
        # Start installation in background thread
        thread = threading.Thread(target=install_thread, daemon=True)
        thread.start()
    
    def get_installation_status(self) -> dict:
        """
        Get the current installation status.
        
        Returns:
            Dictionary with installation status information
        """
        is_installed = self.installer.is_installed()
        current_version = self.installer.get_current_version()
        
        return {
            "is_installed": is_installed,
            "current_version": current_version,
            "is_first_launch": self.is_first_launch(),
            "should_install": self.should_install_yt_dlp(),
            "installer_status": self.installer.status.value,
            "installer_progress": self.installer.progress,
            "installer_message": self.installer.status_message
        }
    
    def check_for_updates(self) -> dict:
        """
        Check for yt-dlp updates.
        
        Returns:
            Dictionary with update information
        """
        try:
            update_info = self.installer.check_for_updates()
            
            return {
                "current_version": update_info.current_version,
                "latest_version": update_info.latest_version,
                "update_available": update_info.update_available,
                "download_url": update_info.download_url,
                "release_notes": update_info.release_notes
            }
        except Exception as e:
            print(f"[DEBUG] Failed to check for updates: {e}")
            return {
                "current_version": "Unknown",
                "latest_version": "Unknown",
                "update_available": False,
                "download_url": "",
                "release_notes": "",
                "error": str(e)
            }
    
    def update_yt_dlp_async(self,
                          progress_callback: Optional[Callable[[InstallerStatus, float, str], None]] = None,
                          completion_callback: Optional[Callable[[bool, str], None]] = None):
        """
        Update yt-dlp asynchronously.
        
        Args:
            progress_callback: Callback for progress updates
            completion_callback: Callback when update completes
        """
        def update_thread():
            try:
                # Create a wrapper callback to match the installer's expected signature
                def wrapper_callback(progress: float, message: str):
                    if progress_callback:
                        progress_callback(InstallerStatus.DOWNLOADING, progress, message)
                
                success = self.installer.install_yt_dlp(wrapper_callback)
                
                if success:
                    message = "yt-dlp updated successfully"
                else:
                    message = "Failed to update yt-dlp"
                
                if completion_callback:
                    completion_callback(success, message)
                    
            except Exception as e:
                print(f"[DEBUG] Update thread error: {e}")
                if completion_callback:
                    completion_callback(False, f"Update error: {str(e)}")
        
        # Start update in background thread
        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()
    
    def get_installation_message(self) -> str:
        """
        Get a user-friendly message about the installation status.
        
        Returns:
            Message describing the current installation status
        """
        status = self.get_installation_status()
        
        if not status["is_installed"]:
            if self.is_first_launch():
                return "Welcome! yt-dlp needs to be installed to download videos."
            else:
                return "yt-dlp is not installed. Please install it to continue."
        
        current_version = status["current_version"]
        if current_version:
            return f"yt-dlp is installed (Version {current_version})"
        else:
            return "yt-dlp is installed but version information is unavailable."
    
    def get_update_message(self) -> str:
        """
        Get a user-friendly message about available updates.
        
        Returns:
            Message describing available updates
        """
        update_info = self.check_for_updates()
        
        if not update_info["update_available"]:
            return "yt-dlp is up to date."
        
        current = update_info["current_version"]
        latest = update_info["latest_version"]
        
        if current == "Unknown":
            return f"Update available: {latest}"
        else:
            return f"Update available: {current} → {latest}"
    
    def cleanup_old_files(self):
        """Clean up old installation files and backups."""
        try:
            self.installer.cleanup_old_backups()
            print("[DEBUG] Cleaned up old installation files")
        except Exception as e:
            print(f"[DEBUG] Failed to cleanup old files: {e}")
    
    def reset_first_launch(self):
        """Reset the first launch flag (for testing purposes)."""
        try:
            flag_file = self.app_data_dir / ".first_launch_complete"
            if flag_file.exists():
                flag_file.unlink()
            print("[DEBUG] Reset first launch flag")
        except Exception as e:
            print(f"[DEBUG] Failed to reset first launch flag: {e}")
    
    def get_config(self) -> FirstLaunchConfig:
        """Get the current configuration."""
        return self.config
    
    def update_config(self, **kwargs):
        """Update the configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._save_config()
        print(f"[DEBUG] Updated first launch config: {kwargs}") 