"""
Version management utilities for YouTube Downloader application.
Handles version comparison, update notifications, and configuration.
"""

import re
import time
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class UpdatePriority(Enum):
    """Priority levels for updates."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VersionInfo:
    """Version information."""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self):
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build:
            version_str += f"+{self.build}"
        return version_str


class VersionManager:
    """
    Handles version parsing, comparison, and update priority determination.
    """
    
    @staticmethod
    def parse_version(version_string: str) -> Optional[VersionInfo]:
        """
        Parse a version string into VersionInfo object.
        
        Args:
            version_string: Version string (e.g., "2023.12.30", "1.2.3-beta")
            
        Returns:
            VersionInfo object or None if parsing fails
        """
        if not version_string:
            return None
        
        # Remove 'v' prefix if present
        version_string = version_string.lstrip('v')
        
        # Basic semantic versioning pattern
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$'
        match = re.match(pattern, version_string)
        
        if not match:
            return None
        
        try:
            major = int(match.group(1))
            minor = int(match.group(2))
            patch = int(match.group(3))
            prerelease = match.group(4)
            build = match.group(5)
            
            return VersionInfo(major, minor, patch, prerelease, build)
        except ValueError:
            return None
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version string
            version2: Second version string
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        v1_info = VersionManager.parse_version(version1)
        v2_info = VersionManager.parse_version(version2)
        
        if not v1_info or not v2_info:
            # Fallback to string comparison
            return (version1 > version2) - (version1 < version2)
        
        # Compare major version
        if v1_info.major != v2_info.major:
            return (v1_info.major > v2_info.major) - (v1_info.major < v2_info.major)
        
        # Compare minor version
        if v1_info.minor != v2_info.minor:
            return (v1_info.minor > v2_info.minor) - (v1_info.minor < v2_info.minor)
        
        # Compare patch version
        if v1_info.patch != v2_info.patch:
            return (v1_info.patch > v2_info.patch) - (v1_info.patch < v2_info.patch)
        
        # Handle prerelease versions
        if v1_info.prerelease is None and v2_info.prerelease is not None:
            return 1  # Release version > prerelease
        elif v1_info.prerelease is not None and v2_info.prerelease is None:
            return -1  # Prerelease < release version
        elif v1_info.prerelease is not None and v2_info.prerelease is not None:
            # Compare prerelease strings
            return (v1_info.prerelease > v2_info.prerelease) - (v1_info.prerelease < v2_info.prerelease)
        
        return 0  # Versions are equal
    
    @staticmethod
    def determine_update_priority(current_version: str, latest_version: str) -> UpdatePriority:
        """
        Determine the priority of an update based on version difference.
        
        Args:
            current_version: Current installed version
            latest_version: Latest available version
            
        Returns:
            UpdatePriority indicating the importance of the update
        """
        if VersionManager.compare_versions(current_version, latest_version) >= 0:
            return UpdatePriority.NONE
        
        current_info = VersionManager.parse_version(current_version)
        latest_info = VersionManager.parse_version(latest_version)
        
        if not current_info or not latest_info:
            return UpdatePriority.MEDIUM  # Default to medium if parsing fails
        
        # Major version update
        if latest_info.major > current_info.major:
            return UpdatePriority.HIGH
        
        # Minor version update
        if latest_info.minor > current_info.minor:
            return UpdatePriority.MEDIUM
        
        # Patch version update
        if latest_info.patch > current_info.patch:
            return UpdatePriority.LOW
        
        # Prerelease to release
        if current_info.prerelease and not latest_info.prerelease:
            return UpdatePriority.MEDIUM
        
        return UpdatePriority.LOW
    
    @staticmethod
    def format_version_display(version: str) -> str:
        """
        Format version string for display.
        
        Args:
            version: Version string
            
        Returns:
            Formatted version string for display
        """
        if not version:
            return "Not installed"
        
        # Remove 'v' prefix and format
        version = version.lstrip('v')
        
        # Add "Version" prefix for clarity
        return f"Version {version}"
    
    @staticmethod
    def get_update_description(current_version: str, latest_version: str) -> str:
        """
        Generate a user-friendly description of the update.
        
        Args:
            current_version: Current installed version
            latest_version: Latest available version
            
        Returns:
            Description of the update
        """
        if VersionManager.compare_versions(current_version, latest_version) >= 0:
            return "You have the latest version installed."
        
        current_info = VersionManager.parse_version(current_version)
        latest_info = VersionManager.parse_version(latest_version)
        
        if not current_info or not latest_info:
            return f"Update available: {current_version} → {latest_version}"
        
        # Major version update
        if latest_info.major > current_info.major:
            return f"Major update available: {current_version} → {latest_version}\nThis update includes significant new features and improvements."
        
        # Minor version update
        if latest_info.minor > current_info.minor:
            return f"Feature update available: {current_version} → {latest_version}\nThis update includes new features and improvements."
        
        # Patch version update
        if latest_info.patch > current_info.patch:
            return f"Bug fix update available: {current_version} → {latest_version}\nThis update includes bug fixes and stability improvements."
        
        return f"Update available: {current_version} → {latest_version}"
    
    @staticmethod
    def should_auto_update(current_version: str, latest_version: str) -> bool:
        """
        Determine if an update should be applied automatically.
        
        Args:
            current_version: Current installed version
            latest_version: Latest available version
            
        Returns:
            True if the update should be automatic
        """
        priority = VersionManager.determine_update_priority(current_version, latest_version)
        
        # Only auto-update for critical and high priority updates
        return priority in [UpdatePriority.CRITICAL, UpdatePriority.HIGH]
    
    @staticmethod
    def get_update_size_estimate(current_version: str, latest_version: str) -> str:
        """
        Get an estimate of the update size.
        
        Args:
            current_version: Current installed version
            latest_version: Latest available version
            
        Returns:
            Estimated size as a string
        """
        # yt-dlp executable is typically around 2-3 MB
        return "~3 MB"
    
    @staticmethod
    def is_version_stable(version: str) -> bool:
        """
        Check if a version is considered stable (not a prerelease).
        
        Args:
            version: Version string to check
            
        Returns:
            True if the version is stable
        """
        version_info = VersionManager.parse_version(version)
        if not version_info:
            return True  # Assume stable if parsing fails
        
        return version_info.prerelease is None 