"""
Core utilities for YouTube Downloader application.
Handles URL validation and playlist probing.
"""

import re
import subprocess
import json
import sys
from typing import Tuple, Optional
from urllib.parse import urlparse, parse_qs
from pathlib import Path


def _find_yt_dlp() -> str:
    """Find yt-dlp executable, prefer app data and bundled version for packaging."""
    from core.first_launch import FirstLaunchManager

    # 1. PyInstaller bundled
    if hasattr(sys, '_MEIPASS'):
        bundled_path = Path(sys._MEIPASS) / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
        if bundled_path.exists():
            return str(bundled_path)

    # 2. App data directory
    manager = FirstLaunchManager()
    installed_path = manager.installer.get_yt_dlp_path()
    if installed_path and installed_path != 'yt-dlp':
        return installed_path

    # 3. Root directory (next to main.py)
    base_path = Path(__file__).parent.parent
    yt_dlp_path = base_path / ('yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
    if yt_dlp_path.exists():
        return str(yt_dlp_path)

    # 4. Fallback: system PATH
    return 'yt-dlp'


def sanitize_url(url: str) -> str:
    """
    Sanitize and validate a URL to prevent command injection and ensure proper structure.
    
    Args:
        url: The URL to sanitize
        
    Returns:
        Sanitized URL string
        
    Raises:
        ValueError: If URL is invalid or contains dangerous patterns
    """
    def log_debug(msg):
        with open('sanitize_url_debug.log', 'a', encoding='utf-8') as f:
            f.write(msg + '\n')

    if not url or not isinstance(url, str):
        log_debug(f"[DEBUG] sanitize_url: url is not a non-empty string: {repr(url)}")
        raise ValueError("URL must be a non-empty string")
    
    # Remove leading/trailing whitespace
    url = url.strip()
    log_debug(f"[DEBUG] sanitize_url: validating url: {repr(url)}")
    
    # Check length limits
    if len(url) > 2048:
        log_debug(f"[DEBUG] sanitize_url: url too long: {len(url)}")
        raise ValueError("URL is too long (maximum 2048 characters)")
    
    # Check for command injection patterns
    dangerous_patterns = [
        ';', '|', '`', '$', '(', ')', '{', '}', '[', ']',
        '&&', '||', '>>', '<<', '>', '<'
    ]
    for pattern in dangerous_patterns:
        if pattern in url:
            log_debug(f"[DEBUG] sanitize_url: url contains dangerous pattern: {pattern}")
            raise ValueError(f"URL contains dangerous pattern: {pattern}")
    
    # Basic URL format validation
    try:
        parsed = urlparse(url)
        log_debug(f"[DEBUG] sanitize_url: parsed.scheme={parsed.scheme}, parsed.netloc={parsed.netloc}, parsed.path={parsed.path}, parsed.query={parsed.query}")
        if not parsed.scheme or not parsed.netloc:
            log_debug(f"[DEBUG] sanitize_url: missing scheme or netloc")
            raise ValueError("Invalid URL format")
    except Exception as e:
        log_debug(f"[DEBUG] sanitize_url: exception in urlparse: {e}")
        raise ValueError(f"Invalid URL format: {e}")
    
    # Check for YouTube domains
    youtube_domains = [
        'youtube.com',
        'www.youtube.com',
        'm.youtube.com',
        'youtu.be',
        'www.youtu.be'
    ]
    if parsed.netloc.lower() not in youtube_domains:
        log_debug(f"[DEBUG] sanitize_url: netloc not in youtube_domains: {parsed.netloc.lower()}")
        raise ValueError("URL must be from a valid YouTube domain")
    
    # Relaxed: For youtube.com, accept any path as long as 'v' or 'list' is present
    if 'youtube.com' in parsed.netloc.lower():
        query_params = parse_qs(parsed.query)
        log_debug(f"[DEBUG] sanitize_url: query_params={query_params}")
        if not ("v" in query_params or "list" in query_params):
            log_debug(f"[DEBUG] sanitize_url: missing 'v' or 'list' in query_params")
            raise ValueError("YouTube URL must contain video ID or playlist ID")
    
    elif 'youtu.be' in parsed.netloc.lower():
        if not parsed.path or len(parsed.path) < 2:
            log_debug(f"[DEBUG] sanitize_url: invalid youtu.be path: {parsed.path}")
            raise ValueError("Invalid youtu.be URL format")
    
    log_debug(f"[DEBUG] sanitize_url: url is valid!")
    return url


def is_valid_url(url: str) -> bool:
    """
    Validate if the given URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid YouTube URL, False otherwise
    """
    try:
        sanitize_url(url)
        return True
    except ValueError:
        return False


def get_playlist_videos(url: str) -> list:
    """
    Get individual video information from a playlist.
    
    Args:
        url: The YouTube playlist URL
        
    Returns:
        List of dictionaries with 'url' and 'title' keys for each video
    """
    if not is_valid_url(url):
        return []
    
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
        
        if result.returncode != 0:
            return []
        
        data = json.loads(result.stdout)
        
        # Check if it's a playlist
        if 'entries' in data:
            videos = []
            entries = data['entries']
            
            for entry in entries:
                if entry is not None:
                    video_info = {
                        'url': entry.get('url', ''),
                        'title': entry.get('title', 'Unknown Video')
                    }
                    if video_info['url']:
                        videos.append(video_info)
            
            return videos
        else:
            # Single video - return as a single-item list
            return [{
                'url': data.get('webpage_url', url),
                'title': data.get('title', 'Unknown Video')
            }]
            
    except subprocess.TimeoutExpired:
        return []
    except (json.JSONDecodeError, subprocess.SubprocessError, Exception):
        return []


def probe_playlist(url: str) -> Tuple[int, Optional[str]]:
    """
    Probe a YouTube URL to determine if it's a playlist and get video count.
    
    Args:
        url: The YouTube URL to probe
        
    Returns:
        Tuple of (video_count, playlist_title)
        - video_count: Number of videos (1 for single video, >1 for playlist)
        - playlist_title: Title of playlist (None for single videos)
    """
    if not is_valid_url(url):
        return 0, None
    
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
        
        if result.returncode != 0:
            return 0, None
        
        data = json.loads(result.stdout)
        
        # Check if it's a playlist
        if 'entries' in data:
            entries = data['entries']
            # Filter out None entries (failed videos)
            valid_entries = [entry for entry in entries if entry is not None]
            count = len(valid_entries)
            title = data.get('title', 'Unknown Playlist')
            return count, title
        else:
            # Single video
            return 1, None
            
    except subprocess.TimeoutExpired:
        return 0, None
    except (json.JSONDecodeError, subprocess.SubprocessError, Exception):
        return 0, None


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