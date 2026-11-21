"""Project storage and workspace manager."""

import json
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.project import Project, ProjectStatus


class ProjectStorageService:
    """Handles structured local filesystem workspaces for each project."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.PROJECTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_project_id(self, project_id: str) -> str:
        """Validates and sanitizes project IDs against directory traversal."""
        if not project_id or not re.match(r"^[a-zA-Z0-9_\-]+$", project_id):
            raise ValueError(f"Invalid project ID: '{project_id}'. Only alphanumeric characters, hyphens, and underscores are allowed.")
        return project_id

    def get_project_dir(self, project_id: str) -> Path:
        """Returns the canonical root directory for a project."""
        clean_id = self._sanitize_project_id(project_id)
        project_dir = (self.base_dir / clean_id).resolve()
        # Verify no path traversal outside base_dir
        if not str(project_dir).startswith(str(self.base_dir.resolve())):
            raise ValueError("Path traversal attempt detected.")
        return project_dir

    def init_project_workspace(self, project_id: str) -> Dict[str, Path]:
        """Creates the full structured folder hierarchy for a project."""
        pdir = self.get_project_dir(project_id)
        dirs = {
            "root": pdir,
            "source": pdir / "source",
            "audio": pdir / "audio",
            "transcript": pdir / "transcript",
            "analysis": pdir / "analysis",
            "clips": pdir / "clips",
            "captions": pdir / "captions",
            "metadata": pdir / "metadata",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    def save_project_metadata(self, project: Project) -> Path:
        """Persists project definition to metadata/project.json."""
        dirs = self.init_project_workspace(project.id)
        meta_file = dirs["metadata"] / "project.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))
        return meta_file

    def load_project_metadata(self, project_id: str) -> Optional[Project]:
        """Loads project definition from metadata/project.json if it exists."""
        pdir = self.get_project_dir(project_id)
        meta_file = pdir / "metadata" / "project.json"
        if not meta_file.exists():
            return None
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Project(**data)

    def list_projects(self) -> List[Project]:
        """Lists all existing projects in the storage base directory."""
        projects = []
        if not self.base_dir.exists():
            return projects
        for item in self.base_dir.iterdir():
            if item.is_dir():
                meta_file = item / "metadata" / "project.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            projects.append(Project(**data))
                    except Exception as e:
                        logger.warning(f"Error loading project {item.name}: {e}")
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def save_stage_checkpoint(self, project_id: str, stage_name: str, data: Dict[str, Any]) -> Path:
        """Saves stage output checkpoint JSON for resumption."""
        dirs = self.init_project_workspace(project_id)
        checkpoint_file = dirs["metadata"] / f"checkpoint_{stage_name}.json"
        payload = {
            "stage": stage_name,
            "project_id": project_id,
            "saved_at": datetime.utcnow().isoformat(),
            "data": data,
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return checkpoint_file

    def load_stage_checkpoint(self, project_id: str, stage_name: str) -> Optional[Dict[str, Any]]:
        """Loads stage output checkpoint JSON if previously completed."""
        pdir = self.get_project_dir(project_id)
        checkpoint_file = pdir / "metadata" / f"checkpoint_{stage_name}.json"
        if not checkpoint_file.exists():
            return None
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
            return payload.get("data")

    def delete_project(self, project_id: str) -> bool:
        """Safely removes an entire project workspace."""
        pdir = self.get_project_dir(project_id)
        if pdir.exists():
            shutil.rmtree(pdir)
            return True
        return False


storage_service = ProjectStorageService()
