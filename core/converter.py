"""
File converter for YouTube Downloader application.
Handles converting downloaded files to different formats with maximum compatibility.
"""

import subprocess
import os
import sys
import threading
from typing import Optional, Callable
from pathlib import Path

from core.utils import sanitize_filename, find_ffmpeg


class ConversionError(Exception):
    """Base exception for conversion errors."""
    pass

class FileNotFoundError(ConversionError):
    """Raised when input file is not found."""
    pass

class OutputError(ConversionError):
    """Raised when output operations fail."""
    pass

class FFmpegError(ConversionError):
    """Raised when ffmpeg operations fail."""
    pass


class FileConverter:
    """
    File converter using ffmpeg for maximum compatibility.
    """
    
    def __init__(self):
        """Initialize the file converter."""
        self._ffmpeg_path = self._find_ffmpeg()
        print(f"[DEBUG] FileConverter: Detected ffmpeg path: {self._ffmpeg_path}")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find ffmpeg executable, prefer bundled version for packaging."""
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path != 'ffmpeg' and os.path.exists(ffmpeg_path):
            return ffmpeg_path
        return None
    
    def convert_file(self, input_path: str, target_format: str, output_folder: str, 
                    progress_callback: Optional[Callable[[float], None]] = None,
                    output_filename: Optional[str] = None) -> str:
        """
        Convert a file to the specified format with maximum compatibility.
        
        Args:
            input_path: Path to the input file
            target_format: Target format ('mp4' or 'mp3')
            output_folder: Output folder path
            progress_callback: Optional callback for progress updates
            output_filename: Optional custom output filename (without extension)
            
        Returns:
            Path to the converted file
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            OutputError: If output folder issues occur
            FFmpegError: If ffmpeg conversion fails
        """
        # Validate input file
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Validate output folder
        if not os.path.exists(output_folder):
            raise OutputError(f"Output folder does not exist: {output_folder}")
        
        if not os.access(output_folder, os.W_OK):
            raise OutputError(f"Output folder is not writable: {output_folder}")
        
        # Generate output filename
        if output_filename:
            # Use custom filename if provided
            if not output_filename.endswith(f'.{target_format}'):
                output_filename = f"{output_filename}.{target_format}"
            sanitized_name = sanitize_filename(output_filename)
            output_path = os.path.join(output_folder, sanitized_name)
        else:
            # Use existing auto-generation logic
            input_filename = os.path.basename(input_path)
            name_without_ext = os.path.splitext(input_filename)[0]
            sanitized_name = sanitize_filename(name_without_ext)
            output_filename = f"{sanitized_name}_converted.{target_format}"
            output_path = os.path.join(output_folder, output_filename)
        
        # Ensure unique filename
        counter = 1
        original_output_path = output_path
        while os.path.exists(output_path):
            name_without_ext = os.path.splitext(original_output_path)[0]
            output_path = f"{name_without_ext}_{counter}.{target_format}"
            counter += 1
        
        # Build ffmpeg command based on target format
        cmd = self._build_conversion_command(input_path, output_path, target_format)
        
        print(f"[DEBUG] FileConverter: Running ffmpeg command: {' '.join(cmd)}")
        
        # Run conversion
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Monitor progress if callback provided
            if progress_callback:
                self._monitor_conversion_progress(process, progress_callback)
            
            # Wait for completion
            return_code = process.wait()
            
            if return_code != 0:
                stderr_output = process.stderr.read() if process.stderr else "Unknown error"
                raise FFmpegError(f"FFmpeg conversion failed (return code {return_code}): {stderr_output}")
            
            # Verify output file exists
            if not os.path.exists(output_path):
                raise FFmpegError("Conversion completed but output file not found")
            
            print(f"[DEBUG] FileConverter: Successfully converted to: {output_path}")
            return output_path
            
        except subprocess.SubprocessError as e:
            raise FFmpegError(f"FFmpeg subprocess error: {e}")
        except Exception as e:
            raise FFmpegError(f"Unexpected error during conversion: {e}")
    
    def _build_conversion_command(self, input_path: str, output_path: str, target_format: str) -> list:
        """
        Build the ffmpeg command for conversion with maximum compatibility.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            target_format: Target format ('mp4' or 'mp3')
            
        Returns:
            List of command arguments
        """
        cmd = [self._ffmpeg_path, '-i', input_path]
        
        if target_format == 'mp4':
            # Maximum compatibility MP4: H.264 video + AAC audio
            cmd.extend([
                '-c:v', 'libx264',      # H.264 video codec
                '-preset', 'medium',     # Balance between speed and compression
                '-crf', '23',           # Constant Rate Factor for quality
                '-c:a', 'aac',          # AAC audio codec
                '-b:a', '128k',         # Audio bitrate
                '-movflags', '+faststart',  # Optimize for web streaming
                '-y'                    # Overwrite output file
            ])
        elif target_format == 'mp3':
            # Maximum compatibility MP3: Standard MP3 format
            cmd.extend([
                '-vn',                  # No video
                '-c:a', 'libmp3lame',   # MP3 audio codec
                '-b:a', '192k',         # Audio bitrate
                '-ar', '44100',         # Sample rate
                '-ac', '2',             # Stereo
                '-y'                    # Overwrite output file
            ])
        else:
            raise ValueError(f"Unsupported target format: {target_format}")
        
        cmd.append(output_path)
        return cmd
    
    def _monitor_conversion_progress(self, process: subprocess.Popen, progress_callback: Callable[[float], None]):
        """
        Monitor conversion progress from ffmpeg output.
        
        Args:
            process: The ffmpeg subprocess
            progress_callback: Callback function for progress updates
        """
        while True:
            if process.stderr is None:
                break
            
            line = process.stderr.readline()
            if not line:
                break
            
            line = line.strip()
            
            # Parse progress from ffmpeg output
            # Example: frame= 1234 fps= 25 q=23.0 size= 1024kB time=00:00:49.36 bitrate= 170.0kbits/s
            if 'time=' in line and 'bitrate=' in line:
                try:
                    # Extract time information
                    time_part = line.split('time=')[1].split()[0]
                    if ':' in time_part:
                        # Convert time to seconds for progress calculation
                        time_parts = time_part.split(':')
                        if len(time_parts) == 3:
                            hours, minutes, seconds = map(float, time_parts)
                            current_time = hours * 3600 + minutes * 60 + seconds
                            
                            # Estimate progress (this is approximate since we don't know total duration)
                            # For now, we'll use a simple progress indicator
                            progress = min(95.0, (current_time / 60.0) * 10)  # Rough estimate
                            progress_callback(progress)
                except (ValueError, IndexError):
                    # Ignore malformed progress lines
                    pass
    
    def get_supported_formats(self) -> dict:
        """
        Get list of supported input and output formats.
        
        Returns:
            Dictionary with supported formats
        """
        return {
            'input_formats': [
                'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm',
                'mp3', 'm4a', 'wav', 'flac', 'ogg', 'aac'
            ],
            'output_formats': ['mp4', 'mp3']
        }
    
    def is_format_supported(self, format_name: str) -> bool:
        """
        Check if a format is supported for conversion.
        
        Args:
            format_name: Format name to check
            
        Returns:
            True if format is supported
        """
        supported = self.get_supported_formats()
        return format_name.lower() in supported['output_formats'] 