#!/usr/bin/env python3
"""
Debug script to test video info extraction
"""

import subprocess
import json
import sys
from pathlib import Path

def test_video_info():
    url = "https://youtu.be/chkOkcEFGM0?si=E13RKzQ1oYSEs46x"
    
    # Find yt-dlp path
    yt_dlp_path = "C:\\Users\\mcgah\\.big_gay_downloader\\yt-dlp\\yt-dlp.exe"
    
    cmd = [
        yt_dlp_path,
        '--quiet',
        '--dump-json',
        '--no-playlist',
        url
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout length: {len(result.stdout)}")
        print(f"Stderr length: {len(result.stderr)}")
        
        if result.stderr:
            print(f"Stderr: {result.stderr}")
        
        if result.returncode == 0:
            try:
                metadata = json.loads(result.stdout)
                print(f"Successfully parsed JSON with {len(metadata)} keys")
                print(f"Title: {metadata.get('title', 'N/A')}")
                return metadata
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"First 500 chars of stdout: {result.stdout[:500]}")
                return None
        else:
            print(f"Command failed with return code {result.returncode}")
            return None
            
    except subprocess.TimeoutExpired:
        print("Command timed out")
        return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_downloader_class():
    print("\n" + "="*50)
    print("Testing Downloader class")
    print("="*50)
    
    try:
        from core.downloader import Downloader
        d = Downloader()
        info = d.get_video_info('https://youtu.be/chkOkcEFGM0?si=E13RKzQ1oYSEs46x')
        print(f"Downloader.get_video_info result: {info}")
        if info:
            print(f"Title from downloader: {info.get('title', 'N/A')}")
        return info
    except Exception as e:
        print(f"Exception in downloader class: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Testing direct subprocess call:")
    metadata = test_video_info()
    if metadata:
        print("Direct subprocess: Success!")
    else:
        print("Direct subprocess: Failed!")
    
    print("\nTesting Downloader class:")
    downloader_result = test_downloader_class()
    if downloader_result:
        print("Downloader class: Success!")
    else:
        print("Downloader class: Failed!") 