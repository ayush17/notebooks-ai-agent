"""Tests for ``sanitize_gcp_field`` (Vertex / GCP string cleanup)."""

import pytest

from devassist.models.config import sanitize_gcp_field


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("itpc-gcp-ai-eng-claude)", "itpc-gcp-ai-eng-claude"),
        ("itpc-gcp-ai-eng-claude/)", "itpc-gcp-ai-eng-claude"),
        ('"my-proj-123",', "my-proj-123"),
        ("  us-central1) ", "us-central1"),
        ("(prod-x)", "prod-x"),
    ],
)
def test_strips_copy_paste_junk(raw: str, expected: str) -> None:
    assert sanitize_gcp_field(raw) == expected


def test_preserves_valid_project_id() -> None:
    assert sanitize_gcp_field("my-team-123") == "my-team-123"
