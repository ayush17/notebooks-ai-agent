"""Unit tests for CVE remediation helpers."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devassist.cve.credentials import resolve_github_token, resolve_jira_auth
from devassist.cve.jira_cve import build_cve_jql
from devassist.cve.mapping_store import load_mappings, mappings_path, save_mappings
from devassist.cve.models import ComponentMapping, RepoEntry
from devassist.cve.scanner_hints import hints_for_repo_path
from devassist.cve.textutil import extract_cve_ids, issue_should_be_ignored


class TestExtractCveIds:
    def test_extracts_multiple(self) -> None:
        text = "See CVE-2024-1234 and cve-2023-9999 for details."
        assert extract_cve_ids(text) == ["CVE-2023-9999", "CVE-2024-1234"]

    def test_empty(self) -> None:
        assert extract_cve_ids("") == []


class TestIgnoreMarkers:
    def test_default_marker(self) -> None:
        assert issue_should_be_ignored(["LGTM", "cve-automation-ignore due to FP"], ())
        assert not issue_should_be_ignored(["LGTM"], ())

    def test_extra_marker(self) -> None:
        assert issue_should_be_ignored(["skip this"], ("skip this",))


class TestBuildCveJql:
    def test_basic(self) -> None:
        jql = build_cve_jql(component="My Component", project_key=None, ignore_resolved=False)
        assert 'component = "My Component"' in jql
        assert 'summary ~ "CVE-"' in jql

    def test_escapes_quotes(self) -> None:
        jql = build_cve_jql(component='Foo "Bar"', project_key=None, ignore_resolved=False)
        assert '\\"' in jql or "Foo" in jql

    def test_project_and_done(self) -> None:
        jql = build_cve_jql(component="c", project_key="PROJ", ignore_resolved=True)
        assert 'project = "PROJ"' in jql
        assert "statusCategory != Done" in jql


class TestMappingsRoundtrip:
    def test_save_load(self, tmp_path: Path) -> None:
        data = {
            "Backend": ComponentMapping(
                repositories={
                    "org/api": RepoEntry(
                        github_url="https://github.com/org/api",
                        default_branch="main",
                        repo_type="upstream",
                    )
                }
            )
        }
        save_mappings(tmp_path, data)
        path = mappings_path(tmp_path)
        assert path.exists()
        loaded = load_mappings(tmp_path)
        assert "Backend" in loaded
        assert loaded["Backend"].repositories["org/api"].default_branch == "main"


class TestCredentials:
    def test_github_token_prefers_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "pat")
        monkeypatch.setenv("GITHUB_TOKEN", "fallback")
        monkeypatch.setattr(
            "devassist.core.env_store.load_devassist_env_into_os",
            lambda **_: None,
        )
        assert resolve_github_token() == "pat"

    def test_jira_auth_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "devassist.core.env_store.load_devassist_env_into_os",
            lambda **_: None,
        )
        monkeypatch.setenv("ATLASSIAN_BASE_URL", "https://example.atlassian.net/")
        monkeypatch.setenv("ATLASSIAN_EMAIL", "a@b.com")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")
        auth = resolve_jira_auth()
        assert auth is not None
        assert auth.base_url == "https://example.atlassian.net"
        assert auth.email == "a@b.com"

    def test_jira_auth_falls_back_to_config_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CVE commands read ``sources.jira`` like ``devassist config add jira``."""
        monkeypatch.setattr(
            "devassist.core.env_store.load_devassist_env_into_os",
            lambda **_: None,
        )
        for key in (
            "ATLASSIAN_BASE_URL",
            "ATLASSIAN_SITE_URL",
            "ATLASSIAN_EMAIL",
            "ATLASSIAN_API_TOKEN",
            "JIRA_URL",
            "JIRA_USERNAME",
            "JIRA_PERSONAL_TOKEN",
        ):
            monkeypatch.delenv(key, raising=False)

        cfg = MagicMock()
        cfg.sources = {
            "jira": {
                "enabled": True,
                "url": "https://team.atlassian.net",
                "email": "me@corp.test",
                "api_token": "yaml-token",
            }
        }

        class _Mgr:
            def load_config(self) -> MagicMock:
                return cfg

        monkeypatch.setattr(
            "devassist.core.config_manager.ConfigManager",
            lambda *_a, **_k: _Mgr(),
        )

        auth = resolve_jira_auth()
        assert auth is not None
        assert auth.base_url == "https://team.atlassian.net"
        assert auth.email == "me@corp.test"
        assert auth.api_token == "yaml-token"


class TestScannerHints:
    def test_go_mod(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module x\n")
        hints = hints_for_repo_path(tmp_path)
        assert any("govulncheck" in h for h in hints)


class TestMappingValidateInvalidJson:
    def test_invalid_json_raises_on_load(self, tmp_path: Path) -> None:
        path = mappings_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_mappings(tmp_path)
