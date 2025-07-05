"""
Core utilities for YouTube Downloader application.
Handles URL validation and playlist probing.
"""

import re
import subprocess
import json
import sys
import os
from typing import Tuple, Optional
from urllib.parse import urlparse, parse_qs
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller onefile.
    """
    if hasattr(sys, '_MEIPASS'):  # type: ignore[attr-defined]
        return os.path.join(sys._MEIPASS, relative_path)  # type: ignore[attr-defined]
    return os.path.join(os.path.abspath("."), relative_path)


def find_ffmpeg() -> str:
    """
    Find ffmpeg executable, prefer bundled version for packaging.
    Returns the path to ffmpeg or 'ffmpeg' as fallback.
    """
    # Try bundled ffmpeg first
    ffmpeg_path = resource_path('assets/ffmpeg/ffmpeg.exe')
    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
    
    # Fallback to system ffmpeg
    return 'ffmpeg'


def _find_yt_dlp() -> str:
    """Find yt-dlp executable, prefer app data and never use PyInstaller temp path."""
    from core.first_launch import FirstLaunchManager

    # 1. App data directory (preferred)
    manager = FirstLaunchManager()
    installed_path = manager.installer.get_yt_dlp_path()
    if installed_path and installed_path != 'yt-dlp':
        # Never use a path from a temp directory (PyInstaller _MEI)
        if '_MEI' not in installed_path:
            return installed_path

    # 2. Root directory (next to main.py)
    base_path = Path(__file__).parent.parent
    yt_dlp_path = base_path / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
    if yt_dlp_path.exists():
        return str(yt_dlp_path)

    # 3. Fallback: system PATH
    return 'yt-dlp'


def sanitize_url(url: str, mode: str = "youtube") -> str:
    """
    Sanitize and validate a URL to prevent command injection and ensure proper structure.
    
    Args:
        url: The URL to sanitize
        mode: Either "youtube" or "xvideos" to determine validation rules
        
    Returns:
        Sanitized URL string
        
    Raises:
        ValueError: If URL is invalid or contains dangerous patterns
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    # Remove leading/trailing whitespace
    url = url.strip()
    
    # Check length limits
    if len(url) > 2048:
        raise ValueError("URL is too long (maximum 2048 characters)")
    
    # Check for command injection patterns
    dangerous_patterns = [
        ';', '|', '`', '$', '(', ')', '{', '}', '[', ']',
        '&&', '||', '>>', '<<', '>', '<'
    ]
    for pattern in dangerous_patterns:
        if pattern in url:
            raise ValueError(f"URL contains dangerous pattern: {pattern}")
    
    # Basic URL format validation
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
    except Exception as e:
        raise ValueError(f"Invalid URL format: {e}")
    
    # Validate based on mode
    if mode == "youtube":
        # Check for YouTube domains
        youtube_domains = [
            'youtube.com',
            'www.youtube.com',
            'm.youtube.com',
            'youtu.be',
            'www.youtu.be'
        ]
        if parsed.netloc.lower() not in youtube_domains:
            raise ValueError("URL must be from a valid YouTube domain")
        
        # Relaxed: For youtube.com, accept any path as long as 'v' or 'list' is present
        if 'youtube.com' in parsed.netloc.lower():
            query_params = parse_qs(parsed.query)
            if not ("v" in query_params or "list" in query_params):
                raise ValueError("YouTube URL must contain video ID or playlist ID")
        
        elif 'youtu.be' in parsed.netloc.lower():
            if not parsed.path or len(parsed.path) < 2:
                raise ValueError("Invalid youtu.be URL format")
    
    elif mode == "xvideos":
        # Check for XVideos domains
        xvideos_domains = [
            'xvideos.com',
            'www.xvideos.com',
            'm.xvideos.com'
        ]
        if parsed.netloc.lower() not in xvideos_domains:
            raise ValueError("URL must be from a valid XVideos domain")
        
        # XVideos URLs typically have paths like /video12345/title
        # Or CDN URLs with specific patterns
        if not parsed.path or len(parsed.path) < 2:
            raise ValueError("Invalid XVideos URL format")
    
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'youtube' or 'xvideos'")
    
    return url


def is_valid_url(url: str, mode: str = "youtube") -> bool:
    """
    Validate if the given URL is a valid URL for the specified mode.
    
    Args:
        url: The URL to validate
        mode: Either "youtube" or "xvideos" to determine validation rules
        
    Returns:
        True if valid URL for the specified mode, False otherwise
    """
    try:
        sanitize_url(url, mode)
        return True
    except ValueError:
        return False


def get_playlist_videos(url: str, mode: str = "youtube") -> Tuple[list, Optional[str], Optional[str]]:
    """
    Get individual video information from a playlist.
    
    Args:
        url: The playlist URL
        mode: Either "youtube" or "xvideos" to determine validation rules
        
    Returns:
        Tuple of (videos_list, error_details, yt_dlp_output)
        - videos_list: List of dictionaries with 'url' and 'title' keys for each video
        - error_details: Detailed error information if failed
        - yt_dlp_output: Raw yt-dlp output (stdout + stderr)
    """
    if not is_valid_url(url, mode):
        return [], "Invalid URL format", None
    
    try:
        # Use bundled yt-dlp to get playlist information with individual video details
        cmd = [
            _find_yt_dlp(),
            '--quiet',
            '--flat-playlist',
            '--dump-single-json',
            url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        # Capture full output for debugging
        full_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nReturn Code: {result.returncode}"
        
        if result.returncode != 0:
            error_msg = f"yt-dlp failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f"\nError: {result.stderr.strip()}"
            return [], error_msg, full_output
        
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse yt-dlp JSON output: {e}\nOutput: {result.stdout[:500]}..."
            return [], error_msg, full_output
        
        videos = []
        
        # Check if it's a playlist
        if 'entries' in data:
            entries = data['entries']
            for entry in entries:
                if entry and isinstance(entry, dict):
                    # For XVideos, use webpage_url to get the original page URL
                    # For other sites, use url as fallback
                    if mode == "xvideos":
                        video_url = entry.get('webpage_url', entry.get('url', ''))
                    else:
                        video_url = entry.get('url', '')
                    
                    video_title = entry.get('title', 'Unknown Title')
                    if video_url:
                        videos.append({
                            'url': video_url,
                            'title': video_title
                        })
        else:
            # Single video
            if mode == "xvideos":
                video_url = data.get('webpage_url', data.get('url', url))
            else:
                video_url = data.get('url', url)
            
            video_title = data.get('title', 'Unknown Title')
            videos.append({
                'url': video_url,
                'title': video_title
            })
        
        return videos, None, full_output
        
    except subprocess.TimeoutExpired:
        return [], "yt-dlp command timed out after 30 seconds", None
    except subprocess.SubprocessError as e:
        return [], f"Subprocess error: {e}", None
    except Exception as e:
        return [], f"Unexpected error: {e}", None


def probe_playlist(url: str, mode: str = "youtube") -> Tuple[int, Optional[str], Optional[str], Optional[str]]:
    """
    Probe a URL to determine if it's a playlist and get video count.
    
    Args:
        url: The URL to probe
        mode: Either "youtube" or "xvideos" to determine validation rules
        
    Returns:
        Tuple of (video_count, playlist_title, error_details, yt_dlp_output)
        - video_count: Number of videos (1 for single video, >1 for playlist, 0 for error)
        - playlist_title: Title of playlist (None for single videos)
        - error_details: Detailed error information if failed
        - yt_dlp_output: Raw yt-dlp output (stdout + stderr)
    """
    if not is_valid_url(url, mode):
        return 0, None, "Invalid URL format", None
    
    try:
        # Use bundled yt-dlp to get playlist information
        cmd = [
            _find_yt_dlp(),
            '--quiet',
            '--flat-playlist',
            '--dump-single-json',
            url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        # Capture full output for debugging
        full_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nReturn Code: {result.returncode}"
        
        if result.returncode != 0:
            error_msg = f"yt-dlp failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f"\nError: {result.stderr.strip()}"
            return 0, None, error_msg, full_output
        
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse yt-dlp JSON output: {e}\nOutput: {result.stdout[:500]}..."
            return 0, None, error_msg, full_output
        
        # Check if it's a playlist
        if 'entries' in data:
            entries = data['entries']
            # Filter out None entries (failed videos)
            valid_entries = [entry for entry in entries if entry is not None]
            count = len(valid_entries)
            title = data.get('title', 'Unknown Playlist')
            return count, title, None, full_output
        else:
            # Single video - check if we need to use webpage_url
            if mode == "xvideos":
                # For XVideos, ensure we're using the original page URL
                video_url = data.get('webpage_url', data.get('url', url))
                # If the URL is a CDN URL, we need to use the original page URL
                if 'cdn' in video_url and 'xvideos-cdn' in video_url:
                    video_url = data.get('webpage_url', url)
            else:
                # For YouTube, use the original URL or webpage_url if available
                video_url = data.get('webpage_url', data.get('url', url))
            
            return 1, None, None, full_output
            
    except subprocess.TimeoutExpired:
        return 0, None, "yt-dlp command timed out after 30 seconds", None
    except subprocess.SubprocessError as e:
        return 0, None, f"Subprocess error: {e}", None
    except Exception as e:
        return 0, None, f"Unexpected error: {e}", None


def validate_output_permissions(folder: str) -> bool:
    """
    Validate that the output folder exists, is writable, and has sufficient disk space.
    
    Args:
        folder: The output folder path to validate
        
    Returns:
        True if folder is valid and writable, False otherwise
    """
    try:
        folder_path = Path(folder)
        
        # Check if folder exists, create if it doesn't
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        
        # Check if it's a directory
        if not folder_path.is_dir():
            return False
        
        # Check write permissions by attempting to create a test file
        test_file = folder_path / ".test_write_permission"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Clean up test file
        except (OSError, PermissionError):
            return False
        
        # Check available disk space (require at least 100MB free)
        try:
            import shutil
            free_space = shutil.disk_usage(folder_path).free
            min_space = 100 * 1024 * 1024  # 100MB in bytes
            if free_space < min_space:
                return False
        except OSError:
            # If we can't check disk space, assume it's OK
            pass
        
        return True
        
    except Exception:
        return False


def safe_filename(filename: str, output_dir: str) -> str:
    """
    Create a safe filename that prevents path traversal and ensures the file stays within the output directory.
    
    Args:
        filename: The original filename
        output_dir: The output directory path
        
    Returns:
        Safe filename that cannot escape the output directory
        
    Raises:
        ValueError: If filename contains path traversal attempts
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Filename must be a non-empty string")
    
    # Convert to absolute paths for comparison
    output_path = Path(output_dir).resolve()
    
    # Create the full path that would result from this filename
    full_path = (output_path / filename).resolve()
    
    # Check if the resulting path is within the output directory
    try:
        full_path.relative_to(output_path)
    except ValueError:
        raise ValueError("Filename contains path traversal attempt")
    
    # Sanitize the filename itself using the original function
    sanitized = _sanitize_filename_internal(filename)
    
    # Double-check the final path is safe
    final_path = (output_path / sanitized).resolve()
    try:
        final_path.relative_to(output_path)
    except ValueError:
        raise ValueError("Sanitized filename still contains path traversal")
    
    return sanitized


def _sanitize_filename_internal(filename: str) -> str:
    """
    Internal sanitization function to avoid recursive calls.
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip(' .')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename or 'untitled'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename safe for filesystem
    """
    return _sanitize_filename_internal(filename)


def safe_error_message(error: Exception) -> str:
    """
    Sanitize error messages to prevent information disclosure.
    
    Args:
        error: The exception to sanitize
        
    Returns:
        User-friendly error message without sensitive information
    """
    error_str = str(error)
    
    # Remove system paths that might contain sensitive information
    import re
    
    # Remove absolute paths
    error_str = re.sub(r'/[A-Za-z]:/[^\\s]*', '[PATH]', error_str)
    error_str = re.sub(r'[A-Za-z]:\\[^\\s]*', '[PATH]', error_str)
    
    # Remove home directory paths
    error_str = re.sub(r'/home/[^\\s]*', '[HOME]', error_str)
    error_str = re.sub(r'C:\\Users\\[^\\s]*', '[HOME]', error_str)
    
    # Remove temporary directory paths
    error_str = re.sub(r'/tmp/[^\\s]*', '[TEMP]', error_str)
    error_str = re.sub(r'C:\\Temp\\[^\\s]*', '[TEMP]', error_str)
    
    # Remove file extensions that might reveal system info
    error_str = re.sub(r'\.exe', '[EXE]', error_str)
    error_str = re.sub(r'\.dll', '[DLL]', error_str)
    error_str = re.sub(r'\.so', '[SO]', error_str)
    
    # Remove process IDs
    error_str = re.sub(r'PID \d+', 'PID [NUMBER]', error_str)
    
    # Remove port numbers
    error_str = re.sub(r':\d{4,5}', ':[PORT]', error_str)
    
    # Common error patterns that should be user-friendly
    error_patterns = {
        'Permission denied': 'Access denied. Please check folder permissions.',
        'No space left on device': 'Insufficient disk space. Please free up some space.',
        'Connection refused': 'Network connection failed. Please check your internet connection.',
        'Timeout': 'Operation timed out. Please try again.',
        'File not found': 'The requested file could not be found.',
        'Invalid URL': 'The provided URL is not valid.',
        'yt-dlp': 'YouTube downloader tool error. Please try again.',
        'ffmpeg': 'Media processing error. Please try again.'
    }
    
    for pattern, replacement in error_patterns.items():
        if pattern.lower() in error_str.lower():
            return replacement
    
    # If no specific pattern matches, return a generic message
    return "An error occurred. Please try again or check your input."


def check_system_resources(output_folder: str) -> dict:
    """
    Check system resources before starting operations.
    
    Args:
        output_folder: The output folder to check
        
    Returns:
        Dictionary with resource status information
    """
    import shutil
    import psutil
    
    status = {
        'disk_space_ok': True,
        'memory_ok': True,
        'network_ok': True,
        'errors': []
    }
    
    try:
        # Check disk space
        folder_path = Path(output_folder)
        if folder_path.exists():
            free_space = shutil.disk_usage(folder_path).free
            min_space = 500 * 1024 * 1024  # 500MB minimum
            if free_space < min_space:
                status['disk_space_ok'] = False
                status['errors'].append(f"Insufficient disk space: {free_space // (1024*1024)}MB free, need at least 500MB")
    except Exception as e:
        status['disk_space_ok'] = False
        status['errors'].append(f"Could not check disk space: {e}")
    
    try:
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 90:  # More than 90% memory used
            status['memory_ok'] = False
            status['errors'].append(f"High memory usage: {memory.percent}%")
    except Exception as e:
        status['memory_ok'] = False
        status['errors'].append(f"Could not check memory: {e}")
    
    try:
        # Check network connectivity (simple ping test)
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except Exception:
        status['network_ok'] = False
        status['errors'].append("No internet connection detected")
    
    return status


def is_adult_content_site(url: str) -> bool:
    """
    Check if the URL is from an adult content site.
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL is from an adult content site, False otherwise
    """
    try:
        parsed = urlparse(url)
        adult_domains = [
            'xvideos.com',
            'www.xvideos.com',
            'm.xvideos.com',
            'pornhub.com',
            'www.pornhub.com',
            'xnxx.com',
            'www.xnxx.com',
            'redtube.com',
            'www.redtube.com',
            'youporn.com',
            'www.youporn.com',
            'spankbang.com',
            'www.spankbang.com',
            'xhamster.com',
            'www.xhamster.com'
        ]
        return parsed.netloc.lower() in adult_domains
    except:
        return False 