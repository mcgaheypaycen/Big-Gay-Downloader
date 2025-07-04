#!/usr/bin/env python3
"""
Test script for yt-dlp installer functionality.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.first_launch import FirstLaunchManager
from core.yt_dlp_installer import InstallerStatus
from core.version_manager import VersionManager


def test_installer():
    """Test the yt-dlp installer functionality."""
    print("Testing yt-dlp installer...")
    
    # Initialize the first launch manager
    manager = FirstLaunchManager()
    
    print(f"App data directory: {manager.app_data_dir}")
    print(f"Is first launch: {manager.is_first_launch()}")
    print(f"Should install yt-dlp: {manager.should_install_yt_dlp()}")
    
    # Check installation status
    status = manager.get_installation_status()
    print(f"Installation status: {status}")
    
    # Check for updates
    update_info = manager.check_for_updates()
    print(f"Update info: {update_info}")
    
    # Test version comparison
    if update_info["current_version"] != "Unknown" and update_info["latest_version"] != "Unknown":
        comparison = VersionManager.compare_versions(
            update_info["current_version"], 
            update_info["latest_version"]
        )
        print(f"Version comparison: {comparison}")
        
        priority = VersionManager.determine_update_priority(
            update_info["current_version"], 
            update_info["latest_version"]
        )
        print(f"Update priority: {priority}")
    
    print("Test completed!")


def test_version_manager():
    """Test the version manager functionality."""
    print("\nTesting version manager...")
    
    # Test version parsing
    test_versions = ["2023.12.30", "2024.1.1", "1.2.3-beta", "2.0.0"]
    
    for version in test_versions:
        parsed = VersionManager.parse_version(version)
        print(f"Parsed '{version}': {parsed}")
    
    # Test version comparison
    comparisons = [
        ("2023.12.30", "2024.1.1"),
        ("2024.1.1", "2023.12.30"),
        ("2023.12.30", "2023.12.30"),
        ("1.2.3-beta", "1.2.3"),
    ]
    
    for v1, v2 in comparisons:
        result = VersionManager.compare_versions(v1, v2)
        print(f"Compare '{v1}' vs '{v2}': {result}")
    
    print("Version manager test completed!")


if __name__ == "__main__":
    test_version_manager()
    test_installer() 