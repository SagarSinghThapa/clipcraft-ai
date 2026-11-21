"""Integration tests for Streamer Facecam detection API route handlers."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException

from backend.app.api.routes_facecam import (
    detect_facecam,
    get_facecam,
    get_facecam_debug_frame,
    FacecamDetectRequest,
)
from backend.app.models.facecam import FacecamRegion
from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.services.storage_service import storage_service


class TestFacecamAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_facecam_api_"))
        self.original_base_dir = storage_service.base_dir
        storage_service.base_dir = self.temp_dir

    def tearDown(self):
        storage_service.base_dir = self.original_base_dir
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_sample_project(self, project_id: str = "proj_test_cam") -> Project:
        dirs = storage_service.init_project_workspace(project_id)
        dummy_video = dirs["source"] / "input.mp4"
        dummy_video.write_bytes(b"dummy video content")

        project = Project(
            id=project_id,
            title="Facecam Test Project",
            source_type=SourceType.LOCAL_FILE,
            source_path=str(dummy_video),
            status=ProjectStatus.INGESTED
        )
        storage_service.save_project_metadata(project)
        return project

    def test_get_facecam_404_for_missing_project(self):
        with self.assertRaises(HTTPException) as ctx:
            get_facecam("nonexistent_123")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_detect_facecam_404_for_missing_project(self):
        with self.assertRaises(HTTPException) as ctx:
            detect_facecam("nonexistent_123")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_detect_facecam_400_when_no_source_file(self):
        project_id = "proj_no_source"
        storage_service.init_project_workspace(project_id)
        project = Project(
            id=project_id,
            title="Empty Project",
            source_type=SourceType.LOCAL_FILE,
            source_path=None,
            status=ProjectStatus.CREATED
        )
        storage_service.save_project_metadata(project)

        with self.assertRaises(HTTPException) as ctx:
            detect_facecam(project_id)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No source video media found", ctx.exception.detail)

    @patch("backend.app.api.routes_facecam.facecam_service.analyze_source_facecam")
    def test_detect_and_get_facecam_success(self, mock_analyze):
        project = self._create_sample_project("proj_cam_success")

        mock_region = FacecamRegion(
            is_detected=True,
            x=1440,
            y=60,
            width=480,
            height=270,
            confidence=0.92,
            quadrant="TOP_RIGHT",
            sample_count=20,
            detected_count=18,
            detected_ratio=0.90,
            video_width=1920,
            video_height=1080
        )
        mock_analyze.return_value = mock_region

        # 1. Trigger detection via route handler
        region = detect_facecam(project.id, FacecamDetectRequest())
        self.assertTrue(region.is_detected)
        self.assertEqual(region.quadrant, "TOP_RIGHT")
        self.assertEqual(region.x, 1440)
        self.assertEqual(region.y, 60)
        self.assertEqual(region.width, 480)
        self.assertEqual(region.height, 270)
        self.assertAlmostEqual(region.confidence, 0.92)

        # 2. Verify cached retrieval via get_facecam
        cached_region = get_facecam(project.id)
        self.assertEqual(cached_region.quadrant, "TOP_RIGHT")
        self.assertEqual(cached_region.width, 480)
        self.assertEqual(cached_region.x, 1440)

        # 3. Verify checkpoint file saved in metadata
        dirs = storage_service.init_project_workspace(project.id)
        checkpoint_path = dirs["metadata"] / "checkpoint_facecam.json"
        self.assertTrue(checkpoint_path.exists())

        # 4. Verify project metadata was updated
        updated_proj = storage_service.load_project_metadata(project.id)
        self.assertIsNotNone(updated_proj.metadata)
        self.assertIsNotNone(updated_proj.metadata.facecam_region)
        self.assertEqual(updated_proj.metadata.facecam_region.quadrant, "TOP_RIGHT")

    def test_get_debug_frame_returns_jpeg(self):
        project = self._create_sample_project("proj_debug_frame")

        # Call get_facecam_debug_frame
        file_response = get_facecam_debug_frame(project.id)
        self.assertEqual(file_response.media_type, "image/jpeg")

        # Verify debug JPEG exists on disk and is a valid JPEG
        debug_path = Path(file_response.path)
        self.assertTrue(debug_path.exists())
        content = debug_path.read_bytes()
        # Standard JPEG magic bytes: FF D8 FF
        self.assertTrue(content.startswith(b"\xff\xd8\xff"))


if __name__ == "__main__":
    unittest.main()
