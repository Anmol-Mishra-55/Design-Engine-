"""
Storage Manager — bucket-only. No local geometry/spec writes.
Directories kept only for logs, cache, temp, and model checkpoints.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages non-artifact local directories (logs, cache, temp, models)."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()
        self.storage_paths = self._initialize_storage_paths()
        self._ensure_directories_exist()

    def _initialize_storage_paths(self) -> Dict[str, Path]:
        return {
            "cache": self.base_dir / "cache",
            "temp": self.base_dir / "temp",
            "models": self.base_dir / "models_ckpt",
            "rl_models": self.base_dir / "models_ckpt" / "opt_ppo",
            "logs": self.base_dir / "reports" / "logs",
        }

    def _ensure_directories_exist(self):
        for name, path in self.storage_paths.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create directory {path}: {e}")

    def get_path(self, path_name: str) -> Path:
        if path_name not in self.storage_paths:
            raise ValueError(f"Unknown storage path: {path_name}")
        return self.storage_paths[path_name]

    def cleanup_temp_files(self, older_than_hours: int = 24):
        import time

        temp_dir = self.get_path("temp")
        cutoff_time = time.time() - (older_than_hours * 3600)
        cleaned = 0
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                cleaned += 1
        logger.info(f"Cleaned up {cleaned} temporary files")
        return cleaned


# Global storage manager instance
storage_manager = StorageManager()


def get_storage_path(path_name: str) -> Path:
    return storage_manager.get_path(path_name)


def ensure_storage_ready():
    storage_manager._ensure_directories_exist()
    logger.info("Storage directories ready (bucket handles all artifacts)")
    return True
