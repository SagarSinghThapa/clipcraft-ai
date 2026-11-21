"""Unit tests for ProjectStorageService and path security."""

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.services.storage_service import ProjectStorageService


class TestProjectStorageService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_clipcraft_"))
        self.service = ProjectStorageService(base_dir=self.temp_dir)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_init_project_workspace_creates_subdirs(self):
        project_id = "proj_test123"
        dirs = self.service.init_project_workspace(project_id)
        self.assertTrue(dirs["root"].exists())
        self.assertTrue(dirs["source"].exists())
        self.assertTrue(dirs["audio"].exists())
        self.assertTrue(dirs["transcript"].exists())
        self.assertTrue(dirs["analysis"].exists())
        self.assertTrue(dirs["clips"].exists())
        self.assertTrue(dirs["captions"].exists())
        self.assertTrue(dirs["metadata"].exists())

    def test_path_traversal_protection(self):
        with self.assertRaises(ValueError):
            self.service.get_project_dir("../evil_path")

        with self.assertRaises(ValueError):
            self.service.get_project_dir("..\\evil_path")

        with self.assertRaises(ValueError):
            self.service.get_project_dir("evil/subfolder")

    def test_save_and_load_project_metadata(self):
        project = Project(
            id="proj_save_load",
            title="Sample Clipping Project",
            source_type=SourceType.LOCAL_FILE,
            source_path="/path/to/video.mp4",
            status=ProjectStatus.CREATED
        )
        self.service.save_project_metadata(project)
        loaded = self.service.load_project_metadata("proj_save_load")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, project.id)
        self.assertEqual(loaded.title, project.title)
        self.assertEqual(loaded.source_type, SourceType.LOCAL_FILE)

    def test_save_and_load_stage_checkpoint(self):
        project_id = "proj_checkpoint_test"
        sample_data = {
            "transcript_text": "Hello world this is a test clip.",
            "duration": 42.5
        }
        self.service.save_stage_checkpoint(project_id, "transcription", sample_data)
        loaded_data = self.service.load_stage_checkpoint(project_id, "transcription")
        self.assertEqual(loaded_data, sample_data)

        # Nonexistent checkpoint returns None
        self.assertIsNone(self.service.load_stage_checkpoint(project_id, "nonexistent"))

    def test_delete_project(self):
        project_id = "proj_to_delete"
        self.service.init_project_workspace(project_id)
        pdir = self.service.get_project_dir(project_id)
        self.assertTrue(pdir.exists())

        deleted = self.service.delete_project(project_id)
        self.assertTrue(deleted)
        self.assertFalse(pdir.exists())


if __name__ == "__main__":
    unittest.main()
