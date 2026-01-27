"""Unit tests for CacheManager.

TDD: These tests are written FIRST and must FAIL before implementation.
"""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from devassist.core.cache_manager import CacheManager


class TestCacheManager:
    """Tests for CacheManager class."""

    def test_init_creates_cache_directory(self, tmp_path: Path) -> None:
        """CacheManager should create cache directory if it doesn't exist."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_get_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        """Should return None when key doesn't exist in cache."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        result = manager.get("nonexistent_key")

        assert result is None

    def test_set_and_get_roundtrip(self, tmp_path: Path) -> None:
        """Should store and retrieve data correctly."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        data = {"items": [1, 2, 3], "name": "test"}
        manager.set("test_key", data)

        result = manager.get("test_key")

        assert result == data

    def test_expired_cache_returns_none(self, tmp_path: Path) -> None:
        """Should return None for expired cache entries."""
        cache_dir = tmp_path / "cache"
        # Short TTL for testing
        manager = CacheManager(cache_dir=cache_dir, ttl_seconds=1)

        manager.set("test_key", {"data": "value"})
        time.sleep(1.5)  # Wait for expiration

        result = manager.get("test_key")

        assert result is None

    def test_default_ttl_is_15_minutes(self, tmp_path: Path) -> None:
        """Default TTL should be 15 minutes (900 seconds)."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        assert manager.ttl_seconds == 900

    def test_cache_by_source_type(self, tmp_path: Path) -> None:
        """Should organize cache by source type."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        gmail_data = {"emails": ["email1", "email2"]}
        slack_data = {"messages": ["msg1", "msg2"]}

        manager.set("gmail:inbox", gmail_data, source_type="gmail")
        manager.set("slack:channel1", slack_data, source_type="slack")

        assert (cache_dir / "gmail").exists()
        assert (cache_dir / "slack").exists()
        assert manager.get("gmail:inbox", source_type="gmail") == gmail_data
        assert manager.get("slack:channel1", source_type="slack") == slack_data

    def test_clear_cache_for_source(self, tmp_path: Path) -> None:
        """Should clear all cache entries for a specific source."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        manager.set("gmail:inbox", {"data": 1}, source_type="gmail")
        manager.set("gmail:sent", {"data": 2}, source_type="gmail")
        manager.set("slack:channel", {"data": 3}, source_type="slack")

        manager.clear_source("gmail")

        assert manager.get("gmail:inbox", source_type="gmail") is None
        assert manager.get("gmail:sent", source_type="gmail") is None
        assert manager.get("slack:channel", source_type="slack") == {"data": 3}

    def test_clear_all_cache(self, tmp_path: Path) -> None:
        """Should clear all cache entries."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir)

        manager.set("gmail:inbox", {"data": 1}, source_type="gmail")
        manager.set("slack:channel", {"data": 2}, source_type="slack")

        manager.clear_all()

        assert manager.get("gmail:inbox", source_type="gmail") is None
        assert manager.get("slack:channel", source_type="slack") is None

    def test_cache_metadata_includes_timestamps(self, tmp_path: Path) -> None:
        """Cache entries should include created_at and expires_at timestamps."""
        cache_dir = tmp_path / "cache"
        manager = CacheManager(cache_dir=cache_dir, ttl_seconds=900)

        before = datetime.now()
        manager.set("test_key", {"data": "value"})
        after = datetime.now()

        metadata = manager.get_metadata("test_key")

        assert metadata is not None
        assert "created_at" in metadata
        assert "expires_at" in metadata
        # expires_at should be ~15 minutes after created_at
        created = datetime.fromisoformat(metadata["created_at"])
        expires = datetime.fromisoformat(metadata["expires_at"])
        assert expires - created == timedelta(seconds=900)
