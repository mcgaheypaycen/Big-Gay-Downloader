#!/usr/bin/env python3
"""
Build script for Big Gay Downloader executable.
Handles PyInstaller build with proper configuration.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_dirs():
    """Clean previous build artifacts."""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)

def verify_requirements():
    """Verify that required files exist."""
    required_files = [
        'main.py',
        'BigGayDownloader.spec',
        'assets/icon.ico',
        'assets/ffmpeg/ffmpeg.exe',
        'core/',
        'ui/'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("ERROR: Missing required files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    print("✓ All required files found")
    return True

def install_pyinstaller():
    """Install PyInstaller if not already installed."""
    try:
        import PyInstaller
        print(f"✓ PyInstaller already installed (version: {PyInstaller.__version__})")
        return True
    except ImportError:
        print("Installing PyInstaller...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller>=5.13.0'], 
                         check=True, capture_output=True)
            print("✓ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install PyInstaller: {e}")
            return False

def build_executable():
    """Build the executable using PyInstaller."""
    print("Building executable...")
    
    try:
        # Run PyInstaller with the spec file
        result = subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            'BigGayDownloader.spec',
            '--clean',
            '--noconfirm'
        ], check=True, capture_output=False)
        
        print("✓ Build completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed: {e}")
        return False

def verify_executable():
    """Verify the built executable exists and has expected size."""
    exe_path = Path('dist/Big Gay Downloader.exe')
    
    if not exe_path.exists():
        print("ERROR: Executable not found at expected location")
        return False
    
    # Check file size (should be reasonable for a bundled app)
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"✓ Executable created: {exe_path}")
    print(f"  Size: {size_mb:.1f} MB")
    
    if size_mb < 10:
        print("WARNING: Executable seems small - may be missing bundled files")
        return False
    
    return True

def main():
    """Main build process."""
    print("=== Big Gay Downloader Build Script ===")
    print()
    
    # Step 1: Clean previous builds
    print("Step 1: Cleaning previous builds...")
    clean_build_dirs()
    
    # Step 2: Verify requirements
    print("\nStep 2: Verifying requirements...")
    if not verify_requirements():
        print("Build failed: Missing required files")
        return False
    
    # Step 3: Install PyInstaller
    print("\nStep 3: Checking PyInstaller...")
    if not install_pyinstaller():
        print("Build failed: Could not install PyInstaller")
        return False
    
    # Step 4: Build executable
    print("\nStep 4: Building executable...")
    if not build_executable():
        print("Build failed: PyInstaller build failed")
        return False
    
    # Step 5: Verify executable
    print("\nStep 5: Verifying executable...")
    if not verify_executable():
        print("Build failed: Executable verification failed")
        return False
    
    print("\n=== Build completed successfully! ===")
    print("Executable location: dist/Big Gay Downloader.exe")
    print("\nNote: On first run, the app will install yt-dlp to the user's app data directory.")
    print("FFmpeg is bundled and ready to use.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 