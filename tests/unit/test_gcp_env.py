"""Tests for GCP project resolution from env and gcloud config files."""

from __future__ import annotations

from pathlib import Path

import pytest

from devassist.utils import gcp_env


def test_resolve_prefers_env_over_gcloud_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "gcloud"
    root.mkdir(parents=True)
    (root / "active_config").write_text("default", encoding="utf-8")
    cfg_dir = root / "configurations"
    cfg_dir.mkdir()
    (cfg_dir / "config_default").write_text(
        "[core]\nproject = from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(root))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-env")
    assert gcp_env.resolve_gcp_project_id() == "from-env"


def test_resolve_reads_gcloud_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for k in (
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCLOUD_PROJECT",
        "GCP_PROJECT",
    ):
        monkeypatch.delenv(k, raising=False)
    root = tmp_path / "gcloud2"
    root.mkdir(parents=True)
    (root / "active_config").write_text("rh", encoding="utf-8")
    cfg_dir = root / "configurations"
    cfg_dir.mkdir()
    (cfg_dir / "config_rh").write_text(
        "[core]\naccount = a@b.com\nproject = itpc-gcp-ai-eng-claude\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(root))
    assert gcp_env.resolve_gcp_project_id() == "itpc-gcp-ai-eng-claude"


def test_adc_path_respects_cloudsdk_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "gcloud3"
    root.mkdir(parents=True)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(root))
    assert gcp_env.application_default_credentials_path() == root / "application_default_credentials.json"
