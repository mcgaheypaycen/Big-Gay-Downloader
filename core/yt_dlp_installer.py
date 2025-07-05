"""
yt-dlp Installer for YouTube Downloader application.
Handles installation, updates, and version management of yt-dlp.
"""

import os
import sys
import json
import shutil
import tempfile
import urllib.request
import urllib.error
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum


class InstallerStatus(Enum):
    """Status of the installer operations."""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class UpdateInfo:
    """Information about available updates."""
    current_version: str
    latest_version: str
    update_available: bool
    download_url: str
    release_notes: str


class YtDlpInstaller:
    """
    Handles yt-dlp installation, updates, and version management.
    """
    
    def __init__(self, app_data_dir: Optional[str] = None):
        """
        Initialize the yt-dlp installer.
        
        Args:
            app_data_dir: Directory to store yt-dlp and configuration
        """
        if app_data_dir is None:
            # Default to user's home directory
            self.app_data_dir = Path.home() / ".big_gay_downloader"
        else:
            self.app_data_dir = Path(app_data_dir)
        
        self.yt_dlp_dir = self.app_data_dir / "yt-dlp"
        self.config_file = self.app_data_dir / "installer_config.json"
        self.backup_dir = self.app_data_dir / "backups"
        
        # Create directories
        self.yt_dlp_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.status = InstallerStatus.IDLE
        self.progress = 0.0
        self.status_message = ""
        self._status_callbacks = []
        
        # Load configuration
        self.config = self._load_config()
        
        print(f"[DEBUG] YtDlpInstaller initialized with data dir: {self.app_data_dir}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load installer configuration."""
        default_config = {
            "last_update_check": 0,
            "auto_update_enabled": True,
            "update_check_interval": 86400,  # 24 hours
            "installed_version": None,
            "installation_date": None
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            print(f"[DEBUG] Failed to load config: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save installer configuration."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[DEBUG] Failed to save config: {e}")
    
    def add_status_callback(self, callback: Callable[[InstallerStatus, float, str], None]):
        """Add a callback for status updates."""
        self._status_callbacks.append(callback)
    
    def _update_status(self, status: InstallerStatus, progress: float = 0.0, message: str = ""):
        """Update status and notify callbacks."""
        self.status = status
        self.progress = progress
        self.status_message = message
        
        for callback in self._status_callbacks:
            try:
                callback(status, progress, message)
            except Exception as e:
                print(f"[DEBUG] Status callback error: {e}")
    
    def get_yt_dlp_path(self) -> Optional[str]:
        """
        Get the path to the installed yt-dlp executable.
        
        Returns:
            Path to yt-dlp executable or None if not found
        """
        # Check bundled version first (for PyInstaller builds)
        if hasattr(sys, '_MEIPASS'):
            bundled_path = Path(sys._MEIPASS) / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
            if bundled_path.exists():
                return str(bundled_path)
        
        # Check installed version
        yt_dlp_exe = self.yt_dlp_dir / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
        if yt_dlp_exe.exists():
            return str(yt_dlp_exe)
        
        # Fallback to system installation
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, timeout=5,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            if result.returncode == 0:
                return 'yt-dlp'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None
    
    def get_current_version(self) -> Optional[str]:
        """
        Get the current version of yt-dlp.
        
        Returns:
            Version string or None if not available
        """
        yt_dlp_path = self.get_yt_dlp_path()
        if not yt_dlp_path:
            return None
        
        try:
            result = subprocess.run([yt_dlp_path, '--version'], 
                                  capture_output=True, text=True, timeout=10,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            if result.returncode == 0:
                version = result.stdout.strip()
                # Update config with current version
                self.config["installed_version"] = version
                self._save_config()
                return version
        except Exception as e:
            print(f"[DEBUG] Failed to get current version: {e}")
        
        return None
    
    def get_latest_version_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the latest yt-dlp release.
        
        Returns:
            Dictionary with release information or None if failed
        """
        try:
            # Get latest release info from GitHub API
            url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
            
            self._update_status(InstallerStatus.CHECKING, 0.0, "Checking for updates...")
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Find the appropriate asset for the current platform
                assets = data.get('assets', [])
                target_asset = None
                
                if sys.platform == 'win32':
                    # Look for Windows executable
                    for asset in assets:
                        if asset['name'] == 'yt-dlp.exe':
                            target_asset = asset
                            break
                else:
                    # Look for Linux/macOS binary
                    for asset in assets:
                        if asset['name'] == 'yt-dlp':
                            target_asset = asset
                            break
                
                if target_asset:
                    return {
                        'version': data['tag_name'].lstrip('v'),
                        'download_url': target_asset['browser_download_url'],
                        'release_notes': data.get('body', ''),
                        'published_at': data.get('published_at', '')
                    }
                
        except Exception as e:
            print(f"[DEBUG] Failed to get latest version info: {e}")
        
        return None
    
    def check_for_updates(self) -> UpdateInfo:
        """
        Check if updates are available.
        
        Returns:
            UpdateInfo object with update status
        """
        current_version = self.get_current_version()
        latest_info = self.get_latest_version_info()
        
        if not current_version:
            return UpdateInfo(
                current_version="Not installed",
                latest_version=latest_info['version'] if latest_info else "Unknown",
                update_available=latest_info is not None,
                download_url=latest_info['download_url'] if latest_info else "",
                release_notes=latest_info['release_notes'] if latest_info else ""
            )
        
        if not latest_info:
            return UpdateInfo(
                current_version=current_version,
                latest_version="Unknown",
                update_available=False,
                download_url="",
                release_notes=""
            )
        
        # Simple version comparison (assumes semantic versioning)
        update_available = self._compare_versions(current_version, latest_info['version']) < 0
        
        return UpdateInfo(
            current_version=current_version,
            latest_version=latest_info['version'],
            update_available=update_available,
            download_url=latest_info['download_url'],
            release_notes=latest_info['release_notes']
        )
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        def version_to_tuple(version):
            parts = version.split('.')
            return tuple(int(part) for part in parts)
        
        try:
            v1_tuple = version_to_tuple(version1)
            v2_tuple = version_to_tuple(version2)
            return (v1_tuple > v2_tuple) - (v1_tuple < v2_tuple)
        except ValueError:
            # If version parsing fails, do string comparison
            return (version1 > version2) - (version1 < version2)
    
    def install_yt_dlp(self, progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
        """
        Install or update yt-dlp.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if installation was successful
        """
        try:
            # Get latest version info
            latest_info = self.get_latest_version_info()
            if not latest_info:
                self._update_status(InstallerStatus.FAILED, 0.0, "Failed to get latest version information")
                return False
            
            # Create backup of existing installation
            if not self._create_backup():
                self._update_status(InstallerStatus.FAILED, 0.0, "Failed to create backup")
                return False
            
            # Download new version
            if not self._download_yt_dlp(latest_info['download_url'], progress_callback):
                self._update_status(InstallerStatus.FAILED, 0.0, "Failed to download yt-dlp")
                return False
            
            # Install the new version
            if not self._install_downloaded_file():
                self._update_status(InstallerStatus.FAILED, 0.0, "Failed to install yt-dlp")
                self._restore_backup()
                return False
            
            # Verify installation
            if not self._verify_installation():
                self._update_status(InstallerStatus.FAILED, 0.0, "Installation verification failed")
                self._restore_backup()
                return False
            
            # Update configuration
            self.config["installed_version"] = latest_info['version']
            self.config["installation_date"] = time.time()
            self.config["last_update_check"] = time.time()
            self._save_config()
            
            self._update_status(InstallerStatus.COMPLETED, 100.0, f"Successfully installed yt-dlp {latest_info['version']}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] Installation failed: {e}")
            self._update_status(InstallerStatus.FAILED, 0.0, f"Installation failed: {str(e)}")
            return False
    
    def _create_backup(self) -> bool:
        """Create backup of existing yt-dlp installation."""
        try:
            current_path = self.get_yt_dlp_path()
            if not current_path or current_path == 'yt-dlp':
                # No local installation to backup
                return True
            
            current_path = Path(current_path)
            if not current_path.exists():
                return True
            
            # Create backup
            backup_path = self.backup_dir / f"yt-dlp_backup_{int(time.time())}.exe"
            shutil.copy2(current_path, backup_path)
            print(f"[DEBUG] Created backup: {backup_path}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] Failed to create backup: {e}")
            return False
    
    def _download_yt_dlp(self, download_url: str, progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
        """Download yt-dlp from the given URL."""
        try:
            self._update_status(InstallerStatus.DOWNLOADING, 0.0, "Downloading yt-dlp...")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.exe' if sys.platform == 'win32' else '')
            temp_path = temp_file.name
            temp_file.close()
            
            # Download with progress
            def download_progress(block_num, block_size, total_size):
                if total_size > 0:
                    progress = (block_num * block_size) / total_size * 100
                    self._update_status(InstallerStatus.DOWNLOADING, progress, f"Downloading... {progress:.1f}%")
                    if progress_callback:
                        progress_callback(progress, f"Downloading... {progress:.1f}%")
            
            urllib.request.urlretrieve(download_url, temp_path, download_progress)
            
            # Verify download
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                os.unlink(temp_path)
                return False
            
            # Move to final location
            final_path = self.yt_dlp_dir / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
            shutil.move(temp_path, final_path)
            
            # Make executable on Unix systems
            if sys.platform != 'win32':
                os.chmod(final_path, 0o755)
            
            print(f"[DEBUG] Downloaded yt-dlp to: {final_path}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] Download failed: {e}")
            return False
    
    def _install_downloaded_file(self) -> bool:
        """Install the downloaded yt-dlp file."""
        try:
            self._update_status(InstallerStatus.INSTALLING, 90.0, "Installing yt-dlp...")
            
            # The file should already be in the correct location
            # Just verify it exists and is executable
            yt_dlp_path = self.yt_dlp_dir / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
            
            if not yt_dlp_path.exists():
                return False
            
            return True
            
        except Exception as e:
            print(f"[DEBUG] Installation failed: {e}")
            return False
    
    def _verify_installation(self) -> bool:
        """Verify that the installation works."""
        try:
            self._update_status(InstallerStatus.INSTALLING, 95.0, "Verifying installation...")
            
            yt_dlp_path = self.get_yt_dlp_path()
            if not yt_dlp_path:
                return False
            
            # Test the installation
            result = subprocess.run([yt_dlp_path, '--version'], 
                                  capture_output=True, text=True, timeout=10,
                                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"[DEBUG] Verification failed: {e}")
            return False
    
    def _restore_backup(self) -> bool:
        """Restore from backup if installation failed."""
        try:
            # Find the most recent backup
            backup_files = list(self.backup_dir.glob("yt-dlp_backup_*.exe"))
            if not backup_files:
                return False
            
            latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
            
            # Restore
            yt_dlp_path = self.yt_dlp_dir / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
            shutil.copy2(latest_backup, yt_dlp_path)
            
            print(f"[DEBUG] Restored from backup: {latest_backup}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] Failed to restore backup: {e}")
            return False
    
    def is_installed(self) -> bool:
        """Check if yt-dlp is installed."""
        return self.get_yt_dlp_path() is not None
    
    def should_check_for_updates(self) -> bool:
        """Check if it's time to check for updates."""
        if not self.config.get("auto_update_enabled", True):
            return False
        
        last_check = self.config.get("last_update_check", 0)
        interval = self.config.get("update_check_interval", 86400)
        
        return time.time() - last_check > interval
    
    def cleanup_old_backups(self, keep_count: int = 3):
        """Clean up old backup files, keeping the most recent ones."""
        try:
            backup_files = list(self.backup_dir.glob("yt-dlp_backup_*.exe"))
            if len(backup_files) <= keep_count:
                return
            
            # Sort by modification time and remove oldest
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            for backup_file in backup_files[keep_count:]:
                backup_file.unlink()
                print(f"[DEBUG] Removed old backup: {backup_file}")
                
        except Exception as e:
            print(f"[DEBUG] Failed to cleanup backups: {e}") 