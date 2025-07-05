"""
Downloader wrapper for YouTube Downloader application.
Handles yt-dlp CLI commands and progress parsing.
"""

import subprocess
import json
import os
import sys
import time
from typing import Optional, Callable
from pathlib import Path

from core.queue import DownloadJob, JobStatus
from core.utils import sanitize_filename, sanitize_url, is_adult_content_site, resource_path, find_ffmpeg


class DownloadError(Exception):
    """Base exception for download errors."""
    pass

class DiskFullError(DownloadError):
    """Raised when disk is full."""
    pass

class NetworkError(DownloadError):
    """Raised when network operations fail."""
    pass

class PermissionError(DownloadError):
    """Raised when permission issues occur."""
    pass

class TemporaryError(DownloadError):
    """Raised for temporary errors that can be retried."""
    pass


class MetadataCache:
    """Simple cache for video metadata to avoid re-fetching."""
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
    
    def get(self, url: str) -> Optional[dict]:
        """Get metadata from cache."""
        return self.cache.get(url)
    
    def set(self, url: str, metadata: dict):
        """Set metadata in cache."""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[url] = metadata
    
    def clear(self):
        """Clear the cache."""
        self.cache.clear()


class Downloader:
    """
    Wrapper for yt-dlp with progress tracking and format selection.
    """
    
    def __init__(self):
        """Initialize the downloader."""
        self._ffmpeg_path = self._find_ffmpeg()
        self._yt_dlp_path = self._find_yt_dlp()
        self._active_processes = []  # Track active subprocesses
        self.metadata_cache = MetadataCache()
        print(f"[DEBUG] Detected ffmpeg path: {self._ffmpeg_path}")
        print(f"[DEBUG] Detected yt-dlp path: {self._yt_dlp_path}")
    
    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable, prefer bundled version for packaging."""
        return find_ffmpeg()
    
    def _find_yt_dlp(self) -> str:
        """Find yt-dlp executable, use existing installer."""
        # Use the existing yt-dlp installer to find the path
        try:
            from core.first_launch import FirstLaunchManager
            manager = FirstLaunchManager()
            yt_dlp_path = manager.installer.get_yt_dlp_path()
            if yt_dlp_path:
                return yt_dlp_path
        except Exception as e:
            print(f"[DEBUG] Failed to get yt-dlp path from installer: {e}")
        
        # Fallback to system yt-dlp
        return 'yt-dlp'
    
    def download_with_retry(self, job: DownloadJob, progress_callback: Optional[Callable] = None, max_retries: int = 3):
        """
        Download a job with retry mechanism for temporary errors.
        
        Args:
            job: The download job to process
            progress_callback: Optional callback for progress updates
            max_retries: Maximum number of retry attempts
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return self.download(job, progress_callback)
            except TemporaryError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    print(f"[DEBUG] Temporary error, retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                    # Reset job status for retry
                    job.status = JobStatus.PENDING
                    job.progress = 0.0
                    job.error_message = None
                else:
                    print(f"[DEBUG] Max retries reached, giving up: {e}")
                    break
            except (DiskFullError, PermissionError, ValueError):
                # These errors should not be retried
                raise
            except Exception as e:
                # Unexpected errors should not be retried
                raise
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception

    def download(self, job: DownloadJob, progress_callback: Optional[Callable] = None):
        """
        Download a video/audio using yt-dlp.
        
        Args:
            job: The download job to process
            progress_callback: Optional callback for progress updates
        """
        print(f"[DEBUG] Downloader: Received job with url={job.url}")
        print(f"[DEBUG] Downloader: Starting download for job: {job.url} (status: {job.status})")
        
        try:
            # Check if job has been cancelled before starting
            if job.status == JobStatus.FAILED:
                print(f"[DEBUG] Downloader: Job {job.url} was cancelled before download started")
                return
            
            # Sanitize and validate the URL
            sanitized_url = sanitize_url(job.url, job.mode)
            print(f"[DEBUG] Downloader: sanitized_url={sanitized_url}")
            
            # First, get video info to extract metadata
            video_info = self.get_video_info(sanitized_url, job.mode)
            if video_info:
                metadata = self._extract_metadata(video_info)
                # Add webpage_url to metadata for enhanced processing
                metadata['webpage_url'] = video_info.get('webpage_url', sanitized_url)
                # Update job title with processed title only if not manually renamed
                if metadata.get('title') and not getattr(job, 'custom_title', None):
                    job.title = metadata['title']
                
                # Use webpage_url for the actual download if available
                download_url = video_info.get('webpage_url', sanitized_url)
                print(f"[DEBUG] Downloader: Using download_url={download_url} (original={sanitized_url})")
            else:
                metadata = {}
                download_url = sanitized_url
                print(f"[DEBUG] Downloader: No video info available, using original URL={download_url}")
            
            # Check again if job was cancelled during metadata fetch
            if job.status == JobStatus.FAILED:
                print(f"[DEBUG] Downloader: Job {job.url} was cancelled during metadata fetch")
                return
            
            # Ensure unique output filename
            unique_output_path = None
            if job.title:
                base_name = sanitize_filename(job.title)
                ext = job.format
                output_folder = job.output_folder
                # Append _compatibility if needed
                if getattr(job, 'compatibility_mode', False):
                    base_name += '_compatibility'
                candidate = os.path.join(output_folder, f"{base_name}.{ext}")
                counter = 1
                while os.path.exists(candidate):
                    candidate = os.path.join(output_folder, f"{base_name}_{counter}.{ext}")
                    counter += 1
                # If we had to add a number, update the job title so yt-dlp uses the unique name
                if counter > 1:
                    job.title = f"{base_name}_{counter-1}"
                else:
                    job.title = base_name
                unique_output_path = candidate
            
            # Build yt-dlp command, passing unique_output_path if set
            output_template = unique_output_path if unique_output_path is not None else os.path.join(job.output_folder, '%(title)s.%(ext)s')
            meta = metadata if video_info else {}
            cmd = self._build_command(download_url, output_template, job, meta)
            print(f"[DEBUG] Downloader: Running yt-dlp command: {' '.join([str(c) for c in cmd])}")
            
            # Final check before starting subprocess
            if job.status == JobStatus.FAILED:
                print(f"[DEBUG] Downloader: Job {job.url} was cancelled before subprocess started")
                return
            
            # Create subprocess with progress tracking
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            print(f"[DEBUG] Downloader: Subprocess started for {job.url}")
            
            # Track the process for cleanup
            self._active_processes.append(process)
            
            try:
                # Monitor progress
                self._monitor_progress(process, job, progress_callback)
                
                # Check if job was cancelled during progress monitoring
                if job.status == JobStatus.FAILED:
                    print(f"[DEBUG] Downloader: Job {job.url} was cancelled during download")
                    return
                
                # Wait for completion
                return_code = process.wait()
                
                # Check if job was cancelled while waiting
                if job.status == JobStatus.FAILED:
                    print(f"[DEBUG] Downloader: Job {job.url} was cancelled while waiting for completion")
                    return
                
                # Always clean up thumbnail files, regardless of return code
                self._cleanup_thumbnail_files(job)
                
                # Check if the download actually succeeded
                # Return code 1 might be due to thumbnail embedding issues, not download failure
                if return_code != 0:
                    stderr_output = process.stderr.read() if process.stderr else ""
                    
                    # Check if the main file was actually downloaded successfully
                    output_path = Path(job.output_folder)
                    if job.title:
                        expected_file = output_path / f"{sanitize_filename(job.title)}.{job.format}"
                    else:
                        # Try to find any file with the correct extension
                        expected_files = list(output_path.glob(f"*.{job.format}"))
                        expected_file = expected_files[0] if expected_files else None
                    
                    if expected_file and expected_file.exists():
                        # File was downloaded successfully, thumbnail embedding just failed
                        print(f"[DEBUG] Downloader: Download succeeded but thumbnail embedding failed: {stderr_output}")
                        job.status = JobStatus.COMPLETED
                        job.progress = 100.0
                    else:
                        # Actual download failure
                        raise Exception(f"Download failed with return code {return_code}: {stderr_output}")
                else:
                    # Clean success
                    print(f"[DEBUG] Downloader: Download completed successfully for {job.url}")
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
            finally:
                # Remove from active processes list
                if process in self._active_processes:
                    self._active_processes.remove(process)
            
        except ValueError as e:
            # URL validation error
            job.status = JobStatus.FAILED
            job.error_message = f"Invalid URL: {str(e)}"
            raise
        except OSError as e:
            # Handle file system errors
            if "No space left on device" in str(e):
                job.status = JobStatus.FAILED
                job.error_message = "Insufficient disk space"
                raise DiskFullError("Insufficient disk space") from e
            elif "Permission denied" in str(e):
                job.status = JobStatus.FAILED
                job.error_message = "Permission denied"
                raise PermissionError("Permission denied") from e
            else:
                job.status = JobStatus.FAILED
                job.error_message = f"File system error: {str(e)}"
                raise
        except subprocess.TimeoutExpired:
            # Handle timeout errors
            job.status = JobStatus.FAILED
            job.error_message = "Operation timed out"
            raise TemporaryError("Operation timed out")
        except subprocess.SubprocessError as e:
            # Handle subprocess errors
            if "Connection" in str(e) or "Network" in str(e):
                job.status = JobStatus.FAILED
                job.error_message = "Network connection failed"
                raise NetworkError("Network connection failed") from e
            else:
                job.status = JobStatus.FAILED
                job.error_message = f"Download tool error: {str(e)}"
                raise TemporaryError(f"Download tool error: {str(e)}") from e
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            raise
    
    def _build_command(self, url: str, output_template: str, job: DownloadJob, metadata: dict) -> list:
        """
        Build the yt-dlp command for the given job.
        
        Args:
            url: The YouTube URL
            output_template: The output filename template
            job: The download job
            metadata: Dictionary containing video information from yt-dlp
            
        Returns:
            List of command arguments
        """
        # Base command - use bundled yt-dlp
        cmd = [self._yt_dlp_path]
        
        # Format selection
        if job.format == 'mp4':
            if getattr(job, 'compatibility_mode', False):
                # Maximum compatibility: download best available and re-encode to H.264/AAC
                cmd.extend([
                    '-f', 'bv*+ba/b',
                    '--merge-output-format', 'mp4',
                    '--recode-video', 'mp4',
                    '--postprocessor-args', 'ffmpeg:-c:v libx264 -c:a aac -strict -2'
                ])
            else:
                # Default: best video + best audio, merged to MP4, force AAC audio for compatibility
                cmd.extend([
                    '-f', 'bv*+ba/b',
                    '--merge-output-format', 'mp4',
                    '--postprocessor-args', 'ffmpeg:-c:a aac'
                ])
        elif job.format == 'mp3':
            if getattr(job, 'compatibility_mode', False):
                # Maximum compatibility: always re-encode to MP3
                cmd.extend([
                    '-f', 'ba',
                    '--extract-audio',
                    '--audio-format', 'mp3',
                    '--audio-quality', '0',
                    '--postprocessor-args', 'ffmpeg:-acodec libmp3lame -ar 44100 -ac 2'
                ])
            else:
                # Default: best audio, extract and convert to MP3
                cmd.extend([
                    '-f', 'ba',
                    '--extract-audio',
                    '--audio-format', 'mp3',
                    '--audio-quality', '0'
                ])
        
        # Output template
        cmd.extend(['-o', output_template])
        
        # Metadata and thumbnail options (make thumbnail embedding optional)
        cmd.extend([
            '--write-thumbnail',  # Download thumbnail
            '--add-metadata',     # Add metadata
        ])
        
        # Only embed thumbnails for audio files (MP3) where it's more useful
        # For MP4, the thumbnail is less critical and can cause ffmpeg issues
        if job.format == 'mp3':
            cmd.append('--embed-thumbnail')  # Embed thumbnail in audio files
        
        # Add specific metadata parsing if available
        if metadata:
            # Use extracted metadata for better parsing
            cmd.extend([
                '--parse-metadata', f'title:{metadata.get("title", "%(title)s")}',
                '--parse-metadata', f'uploader:{metadata.get("artist", "%(uploader)s")}',
                '--parse-metadata', f'channel:{metadata.get("album", "%(channel)s")}',
            ])
            
            # Handle upload_date carefully - adult sites may not provide this
            upload_date = metadata.get("upload_date", "")
            if upload_date and upload_date != "NA" and upload_date != "":
                cmd.extend(['--parse-metadata', f'upload_date:{upload_date}'])
            else:
                # Skip upload_date parsing for adult content sites
                print(f"[DEBUG] Skipping upload_date parsing - not available for this content")
            
            # Add custom metadata fields for artist and album using proper syntax
            if metadata.get("artist"):
                cmd.extend(['--parse-metadata', f'artist:{metadata["artist"]}'])
            if metadata.get("album"):
                cmd.extend(['--parse-metadata', f'album:{metadata["album"]}'])
            
            # Enhanced metadata for XVideos content
            webpage_url = metadata.get('webpage_url', '')
            is_xvideos = 'xvideos.com' in webpage_url if webpage_url else False
            
            if is_xvideos:
                print(f"[DEBUG] Adding enhanced metadata for XVideos content")
                
                # Add keywords/tags
                if metadata.get("keywords"):
                    cmd.extend(['--parse-metadata', f'keywords:{metadata["keywords"]}'])
                
                # Add genre/categories
                if metadata.get("genre"):
                    cmd.extend(['--parse-metadata', f'genre:{metadata["genre"]}'])
                
                # Add view count
                if metadata.get("view_count"):
                    cmd.extend(['--parse-metadata', f'view_count:{metadata["view_count"]}'])
                
                # Add like count
                if metadata.get("like_count"):
                    cmd.extend(['--parse-metadata', f'like_count:{metadata["like_count"]}'])
                
                # Add formatted duration
                if metadata.get("duration_formatted"):
                    cmd.extend(['--parse-metadata', f'duration:{metadata["duration_formatted"]}'])
                
                # Add short description
                if metadata.get("description_short"):
                    cmd.extend(['--parse-metadata', f'description:{metadata["description_short"]}'])
                
                # Add content type and source
                cmd.extend(['--parse-metadata', 'content_type:Adult Content'])
                cmd.extend(['--parse-metadata', 'source_site:XVideos'])
                
                # Add comments field with additional info
                comments_parts = []
                if metadata.get("upload_date_formatted"):
                    comments_parts.append(f"Uploaded: {metadata['upload_date_formatted']}")
                if metadata.get("view_count"):
                    comments_parts.append(f"Views: {metadata['view_count']}")
                if metadata.get("like_count"):
                    comments_parts.append(f"Likes: {metadata['like_count']}")
                if metadata.get("duration_formatted"):
                    comments_parts.append(f"Duration: {metadata['duration_formatted']}")
                
                if comments_parts:
                    comments = " | ".join(comments_parts)
                    cmd.extend(['--parse-metadata', f'comments:{comments}'])
        else:
            # Fallback to basic metadata parsing
            cmd.extend([
                '--parse-metadata', 'title:%(title)s',
                '--parse-metadata', 'uploader:%(uploader)s',
                '--parse-metadata', 'channel:%(channel)s',
            ])
            # Skip upload_date in fallback mode for adult content compatibility
        
        # Performance and stability options
        cmd.extend([
            '--concurrent-fragments', '1',
            '--no-part',
            '--limit-rate', '4M',
            '--no-write-info-json',
            '--no-write-description',
            '--no-mtime'
        ])
        
        # Progress output
        cmd.extend([
            '--progress-template', 'download:%(progress.downloaded_bytes)s/%(progress.total_bytes)s/%(progress.speed)s/%(progress.eta)s'
        ])
        
        # Add ffmpeg path if available
        if self._ffmpeg_path:
            cmd.extend(['--ffmpeg-location', self._ffmpeg_path])
            print(f"[DEBUG] _build_command: Using ffmpeg path: {self._ffmpeg_path}")
        
        # Add URL
        cmd.append(url)
        
        return cmd
    
    def _monitor_progress(self, process: subprocess.Popen, job: DownloadJob, 
                         progress_callback: Optional[Callable] = None):
        """
        Monitor download progress from yt-dlp output.
        
        Args:
            process: The yt-dlp subprocess
            job: The download job
            progress_callback: Optional callback for progress updates
        """
        while True:
            # Check if job has been cancelled
            if job.status == JobStatus.FAILED:
                print(f"[DEBUG] Job {job.url} was cancelled during download, terminating subprocess")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    print(f"[DEBUG] Error terminating cancelled job subprocess: {e}")
                return
            
            # Read output line
            if process.stdout is None:
                break
            line = process.stdout.readline()
            if not line:
                break
            
            line = line.strip()
            
            # Parse progress line
            if line.startswith('download:'):
                try:
                    # Format: download:downloaded_bytes/total_bytes/speed/eta
                    parts = line.split(':', 1)[1].split('/')
                    if len(parts) >= 4:
                        downloaded = int(parts[0]) if parts[0] != 'NA' else 0
                        total = int(parts[1]) if parts[1] != 'NA' else 0
                        speed = parts[2] if parts[2] != 'NA' else None
                        eta = parts[3] if parts[3] != 'NA' else None
                        
                        # Calculate progress percentage
                        if total > 0:
                            progress = (downloaded / total) * 100
                            job.progress = progress
                            
                            # Update speed and ETA
                            if speed:
                                job.speed = speed
                            if eta:
                                job.eta = eta
                            
                            # Call progress callback
                            if progress_callback:
                                progress_callback(job)
                                
                except (ValueError, IndexError):
                    # Ignore malformed progress lines
                    pass
            
            # Check for JSON info (title extraction)
            elif line.startswith('{') and line.endswith('}'):
                try:
                    info = json.loads(line)
                    if 'title' in info and not job.title:
                        job.title = sanitize_filename(info['title'])
                except json.JSONDecodeError:
                    pass
    
    def get_video_info(self, url: str, mode: str = "youtube") -> Optional[dict]:
        """
        Get video information without downloading.
        
        Args:
            url: The URL (should be pre-sanitized)
            mode: Either "youtube" or "xvideos" to determine validation rules
            
        Returns:
            Dictionary with video information or None if failed
        """
        try:
            # URL should already be sanitized, but double-check with mode
            sanitized_url = sanitize_url(url, mode)
            
            # Check cache
            cached_metadata = self.metadata_cache.get(sanitized_url)
            if cached_metadata:
                return cached_metadata
            
            cmd = [
                self._yt_dlp_path,
                '--quiet',
                '--dump-json',
                '--no-playlist',
            ]
            
            # Add ffmpeg path if available
            if self._ffmpeg_path:
                cmd.extend(['--ffmpeg-location', self._ffmpeg_path])
                print(f"[DEBUG] get_video_info: Using ffmpeg path: {self._ffmpeg_path}")
            
            cmd.append(sanitized_url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                # Cache the metadata
                self.metadata_cache.set(sanitized_url, metadata)
                return metadata
            
        except ValueError as e:
            # URL validation error
            print(f"[ERROR] Invalid URL in get_video_info: {e}")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, 
                json.JSONDecodeError, Exception) as e:
            print(f"[ERROR] Failed to get video info: {e}")
        
        return None
    
    def _extract_metadata(self, video_info: dict) -> dict:
        """
        Extract and process metadata from video information.
        
        Args:
            video_info: Dictionary containing video information from yt-dlp
            
        Returns:
            Dictionary with processed metadata
        """
        metadata = {}
        
        # Basic metadata
        metadata['title'] = video_info.get('title', 'Unknown Title')
        metadata['uploader'] = video_info.get('uploader', 'Unknown Artist')
        metadata['channel'] = video_info.get('channel', '')
        metadata['upload_date'] = video_info.get('upload_date', '')
        metadata['description'] = video_info.get('description', '')
        metadata['duration'] = video_info.get('duration', 0)
        
        # Check if this is from an adult content site
        webpage_url = video_info.get('webpage_url', '')
        is_adult_content = is_adult_content_site(webpage_url) if webpage_url else False
        
        # Enhanced metadata extraction for XVideos
        if is_adult_content and 'xvideos.com' in webpage_url:
            print(f"[DEBUG] XVideos content detected, extracting enhanced metadata")
            
            # Extract additional metadata fields
            metadata['artist'] = metadata['uploader']
            metadata['album'] = metadata['uploader']
            
            # Extract tags/keywords from video info
            tags = video_info.get('tags', [])
            if tags:
                metadata['keywords'] = ', '.join(tags)
                print(f"[DEBUG] Extracted tags: {metadata['keywords']}")
            
            # Extract view count
            view_count = video_info.get('view_count', 0)
            if view_count:
                metadata['view_count'] = str(view_count)
                print(f"[DEBUG] Extracted view count: {view_count}")
            
            # Extract like count
            like_count = video_info.get('like_count', 0)
            if like_count:
                metadata['like_count'] = str(like_count)
                print(f"[DEBUG] Extracted like count: {like_count}")
            
            # Extract categories
            categories = video_info.get('categories', [])
            if categories:
                metadata['genre'] = ', '.join(categories)
                print(f"[DEBUG] Extracted categories: {metadata['genre']}")
            
            # Extract upload date in a more readable format
            if metadata['upload_date']:
                try:
                    # Convert YYYYMMDD to YYYY-MM-DD format
                    upload_date = metadata['upload_date']
                    if len(upload_date) == 8:
                        formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                        metadata['upload_date_formatted'] = formatted_date
                        print(f"[DEBUG] Formatted upload date: {formatted_date}")
                except Exception as e:
                    print(f"[DEBUG] Failed to format upload date: {e}")
            
            # Extract video duration in readable format
            if metadata['duration']:
                try:
                    duration_seconds = int(metadata['duration'])
                    minutes = duration_seconds // 60
                    seconds = duration_seconds % 60
                    metadata['duration_formatted'] = f"{minutes}:{seconds:02d}"
                    print(f"[DEBUG] Formatted duration: {metadata['duration_formatted']}")
                except Exception as e:
                    print(f"[DEBUG] Failed to format duration: {e}")
            
            # Extract description (first 200 characters)
            if metadata['description']:
                desc = metadata['description'].strip()
                if len(desc) > 200:
                    desc = desc[:200] + "..."
                metadata['description_short'] = desc
                print(f"[DEBUG] Extracted short description: {desc[:50]}...")
            
            # Set content type/genre
            metadata['content_type'] = 'Adult Content'
            metadata['source_site'] = 'XVideos'
            
        elif is_adult_content:
            # Other adult content sites - basic metadata
            print(f"[DEBUG] Adult content detected, preserving full title: {metadata['title']}")
            metadata['artist'] = metadata['uploader']
            metadata['album'] = metadata['uploader']
            metadata['content_type'] = 'Adult Content'
            
        else:
            # YouTube and other non-adult content - existing logic
            # Try to extract artist and album from title (for music videos)
            title = metadata['title']
            uploader = metadata['uploader']
            
            # Common patterns for music videos
            # Pattern: "Artist - Song Title"
            if ' - ' in title:
                parts = title.split(' - ', 1)
                if len(parts) == 2:
                    metadata['artist'] = parts[0].strip()
                    metadata['title'] = parts[1].strip()
                    metadata['album'] = uploader  # Use uploader as album/channel name
            
            # Pattern: "Song Title (Artist)"
            elif ' (' in title and title.endswith(')'):
                # Extract artist from parentheses
                start = title.rfind(' (')
                if start > 0:
                    artist = title[start + 2:-1].strip()
                    song_title = title[:start].strip()
                    metadata['artist'] = artist
                    metadata['title'] = song_title
                    metadata['album'] = uploader
            
            # Pattern: "Artist: Song Title"
            elif ': ' in title:
                parts = title.split(': ', 1)
                if len(parts) == 2:
                    metadata['artist'] = parts[0].strip()
                    metadata['title'] = parts[1].strip()
                    metadata['album'] = uploader
            
            else:
                # Default: use uploader as artist
                metadata['artist'] = uploader
                metadata['album'] = uploader
            
            # Try to extract album from description or channel
            if not metadata.get('album') or metadata['album'] == uploader:
                # Look for album info in description
                description = metadata['description'].lower()
                if 'album:' in description:
                    album_start = description.find('album:') + 6
                    album_end = description.find('\n', album_start)
                    if album_end == -1:
                        album_end = len(description)
                    album = description[album_start:album_end].strip()
                    if album:
                        metadata['album'] = album.title()
        
        return metadata
    
    def _cleanup_thumbnail_files(self, job: DownloadJob):
        """
        Clean up thumbnail files that were downloaded but not needed.
        
        Args:
            job: The download job
        """
        try:
            # Look for thumbnail files in the output folder
            output_path = Path(job.output_folder)
            
            # Common thumbnail extensions
            thumbnail_extensions = ['.webp', '.jpg', '.jpeg', '.png']
            
            print(f"[DEBUG] Cleaning up thumbnails in: {output_path}")
            
            # Method 1: Try to remove specific thumbnail file based on job title
            if job.title:
                filename_base = sanitize_filename(job.title)
                print(f"[DEBUG] Looking for thumbnails with base: {filename_base}")
                
                for ext in thumbnail_extensions:
                    thumbnail_file = output_path / f"{filename_base}{ext}"
                    if thumbnail_file.exists():
                        thumbnail_file.unlink()
                        print(f"[DEBUG] Removed specific thumbnail: {thumbnail_file}")
            
            # Method 2: Remove any thumbnail files in the folder (more aggressive cleanup)
            print(f"[DEBUG] Scanning for any thumbnail files...")
            for ext in thumbnail_extensions:
                for thumbnail_file in output_path.glob(f"*{ext}"):
                    if thumbnail_file.exists():
                        # Check if it's actually a thumbnail (not the main video file)
                        if not thumbnail_file.name.lower().endswith(('.mp3', '.mp4', '.m4a', '.webm')):
                            thumbnail_file.unlink()
                            print(f"[DEBUG] Removed thumbnail: {thumbnail_file}")
            
            # Method 3: Look for files with common thumbnail patterns
            # yt-dlp sometimes uses patterns like "title.thumb.webp" or "title.thumbnail.webp"
            if job.title:
                filename_base = sanitize_filename(job.title)
                for ext in thumbnail_extensions:
                    # Try various thumbnail naming patterns
                    patterns = [
                        f"{filename_base}.thumb{ext}",
                        f"{filename_base}.thumbnail{ext}",
                        f"{filename_base}_thumb{ext}",
                        f"{filename_base}_thumbnail{ext}",
                        f"thumb_{filename_base}{ext}",
                        f"thumbnail_{filename_base}{ext}"
                    ]
                    
                    for pattern in patterns:
                        thumbnail_file = output_path / pattern
                        if thumbnail_file.exists():
                            thumbnail_file.unlink()
                            print(f"[DEBUG] Removed pattern thumbnail: {thumbnail_file}")
                            
        except Exception as e:
            # Don't fail the download if cleanup fails
            print(f"[DEBUG] Thumbnail cleanup failed: {e}")
            pass
    
    def cleanup_subprocesses(self):
        """Clean up all active subprocesses."""
        for process in self._active_processes:
            try:
                if process.poll() is None:  # Process is still running
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Wait up to 5 seconds
                    except subprocess.TimeoutExpired:
                        process.kill()  # Force kill if it doesn't terminate
            except Exception as e:
                print(f"[DEBUG] Error cleaning up process: {e}")
        
        self._active_processes.clear()
    
    def __del__(self):
        """Cleanup when the downloader is destroyed."""
        self.cleanup_subprocesses() 