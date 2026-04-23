"""Tests for ``~/.devassist/env`` helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from devassist.core import env_store


def test_merge_updates_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_store.merge_devassist_env_updates({"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test"})
    data = env_store.read_devassist_env_dict()
    assert data.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "ghp_test"
    env_store.merge_devassist_env_updates({"FOO_BAR": "baz"})
    data2 = env_store.read_devassist_env_dict()
    assert data2.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "ghp_test"
    assert data2.get("FOO_BAR") == "baz"


def test_load_prefer_file_overrides_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / ".devassist" / "env"
    p.parent.mkdir(parents=True)
    p.write_text('export MYKEY="from-file"\n', encoding="utf-8")
    monkeypatch.setenv("MYKEY", "from-shell")
    env_store.load_devassist_env_into_os(prefer_file=True)
    assert os.environ["MYKEY"] == "from-file"


def test_source_config_from_env_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "patx")
    assert env_store.source_config_from_env("github") == {"personal_access_token": "patx"}


def test_canonical_env_overrides_legacy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    base = tmp_path / ".devassist"
    base.mkdir(parents=True)
    (base / ".env").write_text('export FOO="legacy"\n', encoding="utf-8")
    (base / "env").write_text('export FOO="canonical"\n', encoding="utf-8")
    assert env_store.read_devassist_env_dict()["FOO"] == "canonical"


def test_write_mirrors_legacy_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_store.write_devassist_env_from_dict({"ZZZ_MIRROR": "x"})
    env_path = tmp_path / ".devassist" / "env"
    legacy_path = tmp_path / ".devassist" / ".env"
    assert env_path.is_file() and legacy_path.is_file()
    assert "ZZZ_MIRROR" in legacy_path.read_text(encoding="utf-8")


def test_load_syncs_github_token_alias(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "tok-only")
    p = tmp_path / ".devassist" / "env"
    p.parent.mkdir(parents=True)
    p.write_text("# empty\n", encoding="utf-8")
    env_store.load_devassist_env_into_os(prefer_file=True)
    assert os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "tok-only"
