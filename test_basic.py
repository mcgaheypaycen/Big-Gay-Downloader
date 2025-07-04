"""
Basic tests for YouTube Downloader core functionality.
"""

import unittest
from core.utils import is_valid_url, sanitize_filename
from core.queue import DownloadJob, JobStatus


class TestUtils(unittest.TestCase):
    """Test utility functions."""
    
    def test_is_valid_url(self):
        """Test URL validation."""
        # Valid URLs
        self.assertTrue(is_valid_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_valid_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(is_valid_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_valid_url("http://youtube.com/watch?v=dQw4w9WgXcQ"))  # HTTP is also valid
        
        # Invalid URLs
        self.assertFalse(is_valid_url(""))
        self.assertFalse(is_valid_url("not a url"))
        self.assertFalse(is_valid_url("https://example.com/video"))
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test invalid characters (there are 8 invalid chars: < > : " / \ | ? *)
        self.assertEqual(sanitize_filename("file<>:\"/\\|?*.txt"), "file_________.txt")
        
        # Test leading/trailing spaces and dots
        self.assertEqual(sanitize_filename("  file.txt  "), "file.txt")
        self.assertEqual(sanitize_filename("...file.txt..."), "file.txt")
        
        # Test empty filename
        self.assertEqual(sanitize_filename(""), "untitled")
        
        # Test long filename
        long_name = "a" * 300
        sanitized = sanitize_filename(long_name)
        self.assertLessEqual(len(sanitized), 200)


class TestDownloadJob(unittest.TestCase):
    """Test DownloadJob class."""
    
    def test_download_job_creation(self):
        """Test creating a download job."""
        job = DownloadJob(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            format="mp4",
            output_folder="/tmp"
        )
        
        self.assertEqual(job.url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(job.format, "mp4")
        self.assertEqual(job.output_folder, "/tmp")
        self.assertEqual(job.status, JobStatus.PENDING)
        self.assertEqual(job.progress, 0.0)
        self.assertIsNone(job.error_message)
        self.assertIsNone(job.title)
        self.assertIsNone(job.eta)
        self.assertIsNone(job.speed)
        self.assertIsNone(job.progress_widgets)


if __name__ == "__main__":
    unittest.main() 