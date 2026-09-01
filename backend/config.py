"""Configuration and immutable artifact paths for the API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    frontend_origins: tuple[str, ...]

    @property
    def calibrated_model_path(self) -> Path:
        return self.project_root / "models" / "smart_retry_calibrated_model.joblib"

    @property
    def evaluation_dir(self) -> Path:
        return self.project_root / "evaluation"

    @property
    def source_dataset_path(self) -> Path:
        return self.project_root / "data" / "raw" / "final_prototype_100k_corrected.csv"


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    configured = os.getenv("FRONTEND_ORIGIN", "http://localhost:8080")
    origins = tuple(origin.strip() for origin in configured.split(",") if origin.strip())
    return Settings(project_root=root, frontend_origins=origins)
