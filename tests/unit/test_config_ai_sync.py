"""Tests for YAML ``ai`` sync from ``~/.devassist/env``."""

from __future__ import annotations

from pathlib import Path

import pytest

from devassist.core.config_manager import ConfigManager, infer_ai_updates_from_env


def test_infer_vertex_maps_to_gemini() -> None:
    u = infer_ai_updates_from_env(
        {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-proj",
            "CLOUD_ML_REGION": "us-east5",
        }
    )
    assert u["provider"] == "gemini"
    assert u["project_id"] == "my-proj"
    assert u["location"] == "us-east5"


def test_infer_api_key_maps_to_anthropic() -> None:
    assert infer_ai_updates_from_env({"ANTHROPIC_API_KEY": "sk-ant"}) == {"provider": "anthropic"}


def test_infer_explicit_provider_in_env_file() -> None:
    assert infer_ai_updates_from_env({"DEVASSIST_AI_PROVIDER": "gemini"}) == {"provider": "gemini"}


@pytest.mark.parametrize(
    ("env_keys", "expected_empty"),
    [
        ({}, True),
        ({"CLAUDE_CODE_USE_VERTEX": "1"}, True),
    ],
)
def test_infer_empty_when_insufficient(env_keys: dict[str, str], expected_empty: bool) -> None:
    out = infer_ai_updates_from_env(env_keys)
    assert (len(out) == 0) == expected_empty


def test_sync_writes_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_dir = tmp_path / ".devassist"
    env_dir.mkdir(parents=True)
    (env_dir / "env").write_text(
        "\n".join(
            [
                'export CLAUDE_CODE_USE_VERTEX="1"',
                'export ANTHROPIC_VERTEX_PROJECT_ID="sync-proj"',
                'export CLOUD_ML_REGION="us-central1"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    cm = ConfigManager(workspace_dir=env_dir)
    assert cm.sync_ai_yaml_from_env_store() is True
    cfg = cm.load_config()
    assert cfg.ai.provider == "gemini"
    assert cfg.ai.project_id == "sync-proj"
