"""Resolve GCP project and ADC paths from the environment and ``gcloud`` config."""

from __future__ import annotations

import os
from configparser import ConfigParser
from pathlib import Path

from devassist.models.config import sanitize_gcp_field


def gcloud_config_dir() -> Path:
    """Directory holding ``active_config``, ``configurations/``, and ADC JSON."""
    raw = (os.environ.get("CLOUDSDK_CONFIG") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config" / "gcloud"


def application_default_credentials_path() -> Path:
    """Path to Application Default Credentials JSON (after ``gcloud auth application-default login``)."""
    return gcloud_config_dir() / "application_default_credentials.json"


def read_gcloud_config_project() -> str:
    """Read ``core.project`` from the active gcloud configuration profile.

    Used when ``GOOGLE_CLOUD_PROJECT`` / ``ANTHROPIC_VERTEX_PROJECT_ID`` etc. are not set
    but the user has run ``gcloud config set project ...``.
    """
    root = gcloud_config_dir()
    active = root / "active_config"
    if not active.is_file():
        return ""
    profile = active.read_text(encoding="utf-8").strip()
    if not profile:
        return ""
    cfg_path = root / "configurations" / f"config_{profile}"
    if not cfg_path.is_file():
        return ""
    parser = ConfigParser(interpolation=None)
    try:
        parser.read(cfg_path, encoding="utf-8")
    except OSError:
        return ""
    raw = parser.get("core", "project", fallback="").strip()
    return sanitize_gcp_field(raw)


def resolve_gcp_project_id() -> str:
    """Best-effort GCP project id: env vars first, then active gcloud profile."""
    for key in (
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCLOUD_PROJECT",
        "GCP_PROJECT",
    ):
        if raw := os.environ.get(key):
            s = sanitize_gcp_field(raw)
            if s:
                return s
    return read_gcloud_config_project()
