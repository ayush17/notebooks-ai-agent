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
from devassist.cve.artifacts import render_ai_triage_readme
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


class TestAiTriageReadme:
    def test_groups_by_cve_and_dedupes_table(self) -> None:
        body = render_ai_triage_readme(
            component="MySvc",
            jql='labels = "CVE"',
            issues=[
                {
                    "key": "P-1",
                    "summary": "Fix CVE-2024-1000",
                    "cves": ["CVE-2024-1000"],
                    "browse_url": "https://jira/browse/P-1",
                    "status": "Open",
                    "priority": "High",
                    "issuetype": "Bug",
                    "duedate": "2026-04-10",
                    "labels": "CVE",
                },
                {
                    "key": "P-2",
                    "summary": "also CVE-2024-1000",
                    "cves": ["CVE-2024-1000"],
                    "browse_url": "https://jira/browse/P-2",
                    "status": "To Do",
                    "priority": "Medium",
                    "issuetype": "Task",
                    "duedate": "2026-05-01",
                    "labels": "",
                },
            ],
            generated_at_utc="2026-04-23T12:00:00Z",
        )
        assert body.count("## AI Retriage Update -") == 1
        assert "CVE: CVE-2024-1000 —" in body
        assert "Severity: High, Medium" in body
        assert "Due date: 2026-04-10" in body
        assert "Updated verdict: pending-triage" in body
        assert "RHOAI Product Impact" in body
        assert "Representative built-image evidence" in body
        assert "Why this is still not AI-fixable" in body
        assert "Recommended next step" in body
        assert "P-1" in body and "P-2" in body
        assert "nvd.nist.gov" in body

    def test_bare_issues_section_when_no_cve_in_text(self) -> None:
        body = render_ai_triage_readme(
            component="C",
            jql="x",
            issues=[
                {
                    "key": "P-9",
                    "summary": "no id here",
                    "cves": [],
                    "browse_url": "https://jira/browse/P-9",
                    "status": "",
                    "priority": "",
                    "issuetype": "",
                    "duedate": "",
                    "labels": "",
                }
            ],
            generated_at_utc="2026-04-23T12:00:00Z",
        )
        assert "without a CVE id" in body


class TestBuildCveJql:
    def test_basic(self) -> None:
        jql = build_cve_jql(component="My Component", project_key=None, ignore_resolved=False)
        assert 'component = "My Component"' in jql
        assert 'labels = "CVE"' in jql

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
