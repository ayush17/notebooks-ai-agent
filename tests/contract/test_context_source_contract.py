"""Contract tests for ContextSourceAdapter.

TDD: These tests define the contract that ALL adapters must fulfill.
Any adapter implementation must pass these tests.
"""

import pytest
from abc import ABC
from datetime import datetime
from typing import AsyncIterator

from devassist.adapters.base import ContextSourceAdapter
from devassist.adapters.errors import AuthenticationError, SourceUnavailableError
from devassist.models.context import ContextItem, SourceType


class TestContextSourceAdapterContract:
    """Contract tests that all adapters must satisfy."""

    def test_adapter_has_source_type_property(self) -> None:
        """All adapters must have a source_type property returning SourceType."""
        # This test verifies the abstract base class structure
        assert hasattr(ContextSourceAdapter, "source_type")

    def test_adapter_has_display_name_property(self) -> None:
        """All adapters must have a display_name property."""
        assert hasattr(ContextSourceAdapter, "display_name")

    def test_adapter_has_authenticate_method(self) -> None:
        """All adapters must have an authenticate method."""
        assert hasattr(ContextSourceAdapter, "authenticate")
        # Should be async
        import inspect
        assert inspect.iscoroutinefunction(ContextSourceAdapter.authenticate)

    def test_adapter_has_test_connection_method(self) -> None:
        """All adapters must have a test_connection method."""
        assert hasattr(ContextSourceAdapter, "test_connection")
        import inspect
        assert inspect.iscoroutinefunction(ContextSourceAdapter.test_connection)

    def test_adapter_has_fetch_items_method(self) -> None:
        """All adapters must have a fetch_items method."""
        assert hasattr(ContextSourceAdapter, "fetch_items")

    def test_adapter_has_get_required_config_fields_method(self) -> None:
        """All adapters must have get_required_config_fields method."""
        assert hasattr(ContextSourceAdapter, "get_required_config_fields")


class TestContextItemContract:
    """Contract tests for ContextItem data structure."""

    def test_context_item_has_required_fields(self) -> None:
        """ContextItem must have all required fields."""
        item = ContextItem(
            id="test-123",
            source_id="gmail-1",
            source_type=SourceType.GMAIL,
            timestamp=datetime.now(),
            title="Test Email",
            content="Test content",
            relevance_score=0.5,
        )

        assert item.id == "test-123"
        assert item.source_id == "gmail-1"
        assert item.source_type == SourceType.GMAIL
        assert isinstance(item.timestamp, datetime)
        assert item.title == "Test Email"
        assert item.relevance_score == 0.5

    def test_context_item_relevance_score_bounds(self) -> None:
        """Relevance score must be between 0.0 and 1.0."""
        # Valid scores
        item_low = ContextItem(
            id="1", source_id="s1", source_type=SourceType.GMAIL,
            timestamp=datetime.now(), title="Test", relevance_score=0.0
        )
        item_high = ContextItem(
            id="2", source_id="s1", source_type=SourceType.GMAIL,
            timestamp=datetime.now(), title="Test", relevance_score=1.0
        )

        assert item_low.relevance_score == 0.0
        assert item_high.relevance_score == 1.0

        # Invalid scores should raise validation error
        with pytest.raises(ValueError):
            ContextItem(
                id="3", source_id="s1", source_type=SourceType.GMAIL,
                timestamp=datetime.now(), title="Test", relevance_score=1.5
            )

        with pytest.raises(ValueError):
            ContextItem(
                id="4", source_id="s1", source_type=SourceType.GMAIL,
                timestamp=datetime.now(), title="Test", relevance_score=-0.1
            )

    def test_context_item_optional_fields(self) -> None:
        """Optional fields should have sensible defaults."""
        item = ContextItem(
            id="test-123",
            source_id="gmail-1",
            source_type=SourceType.GMAIL,
            timestamp=datetime.now(),
            title="Test",
            relevance_score=0.5,
        )

        assert item.content is None
        assert item.url is None
        assert item.author is None
        assert item.metadata == {}
        assert item.is_read is False


class TestSourceTypeContract:
    """Contract tests for SourceType enum."""

    def test_source_type_has_mvp_values(self) -> None:
        """SourceType must include all MVP sources."""
        assert SourceType.GMAIL.value == "gmail"
        assert SourceType.SLACK.value == "slack"
        assert SourceType.JIRA.value == "jira"
        assert SourceType.GITHUB.value == "github"

    def test_source_type_is_string_enum(self) -> None:
        """SourceType values should be strings for serialization."""
        for source in SourceType:
            assert isinstance(source.value, str)
