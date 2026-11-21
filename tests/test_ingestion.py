"""Unit tests for media ingestion and FFmpeg utilities."""

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.services.storage_service import ProjectStorageService
from backend.app.services.ingestion_service import IngestionService
from backend.app.utils.ffmpeg_utils import escape_ffmpeg_path, probe_media_metadata


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_ingest_"))
        self.storage = ProjectStorageService(base_dir=self.temp_dir)
        self.service = IngestionService()

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_escape_ffmpeg_path_windows(self):
        # Forward slashes with colon escaping
        p = Path("C:/videos/project/subtitles.ass")
        escaped = escape_ffmpeg_path(p)
        self.assertTrue("C\\:" in escaped or "C:" in escaped)
        self.assertNotIn("\\", escaped.replace("C\\:", ""))

    def test_youtube_url_validator(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ&t=10s",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        ]
        for url in valid_urls:
            self.assertTrue(self.service.validate_youtube_url(url), f"Failed for valid URL: {url}")

        invalid_urls = [
            "https://vimeo.com/123456",
            "https://evil.com/video.mp4",
            "file:///etc/passwd",
            "not_a_url",
            ""
        ]
        for url in invalid_urls:
            self.assertFalse(self.service.validate_youtube_url(url), f"Should fail for invalid URL: {url}")

    def test_unsupported_local_extension(self):
        dummy_file = self.temp_dir / "unsupported.txt"
        dummy_file.write_text("not a video")

        project = Project(
            id="proj_ext_test",
            title="Ext Test",
            source_type=SourceType.LOCAL_FILE,
            status=ProjectStatus.CREATED
        )
        self.storage.save_project_metadata(project)

        with self.assertRaises(ValueError):
            self.service.ingest_local_file("proj_ext_test", str(dummy_file))

    def test_nonexistent_local_file(self):
        with self.assertRaises(FileNotFoundError):
            self.service.ingest_local_file("proj_ext_test", str(self.temp_dir / "ghost.mp4"))


if __name__ == "__main__":
    unittest.main()
