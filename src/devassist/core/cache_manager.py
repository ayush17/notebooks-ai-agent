"""Cache manager for DevAssist.

Handles caching of context items with TTL-based expiration.
"""

import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class CacheManager:
    """Manages JSON file-based caching with TTL support."""

    DEFAULT_TTL_SECONDS = 900  # 15 minutes

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Initialize CacheManager.

        Args:
            cache_dir: Path to cache directory. Defaults to ~/.devassist/cache
            ttl_seconds: Cache TTL in seconds. Defaults to 900 (15 minutes).
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".devassist" / "cache"
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS
        self._ensure_cache_dir_exists()

    def _ensure_cache_dir_exists(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str, source_type: str | None = None) -> Path:
        """Get path to cache file for a key.

        Args:
            key: Cache key.
            source_type: Optional source type for organization.

        Returns:
            Path to cache file.
        """
        # Create safe filename from key
        safe_key = hashlib.md5(key.encode()).hexdigest()

        if source_type:
            source_dir = self.cache_dir / source_type
            source_dir.mkdir(parents=True, exist_ok=True)
            return source_dir / f"{safe_key}.json"

        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, source_type: str | None = None) -> Any | None:
        """Get cached data if not expired.

        Args:
            key: Cache key.
            source_type: Optional source type for lookup.

        Returns:
            Cached data or None if not found or expired.
        """
        cache_path = self._get_cache_path(key, source_type)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                cached = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(cached.get("expires_at", ""))
        if datetime.now() > expires_at:
            # Cache expired, remove file
            cache_path.unlink(missing_ok=True)
            return None

        return cached.get("data")

    def set(
        self,
        key: str,
        data: Any,
        source_type: str | None = None,
    ) -> None:
        """Store data in cache.

        Args:
            key: Cache key.
            data: Data to cache (must be JSON serializable).
            source_type: Optional source type for organization.
        """
        cache_path = self._get_cache_path(key, source_type)
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=self.ttl_seconds)

        cache_entry = {
            "key": key,
            "data": data,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        with open(cache_path, "w") as f:
            json.dump(cache_entry, f, indent=2)

    def get_metadata(self, key: str, source_type: str | None = None) -> dict[str, Any] | None:
        """Get cache entry metadata without the data.

        Args:
            key: Cache key.
            source_type: Optional source type for lookup.

        Returns:
            Metadata dict with created_at and expires_at, or None.
        """
        cache_path = self._get_cache_path(key, source_type)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                cached = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        return {
            "created_at": cached.get("created_at"),
            "expires_at": cached.get("expires_at"),
        }

    def clear_source(self, source_type: str) -> None:
        """Clear all cache entries for a specific source.

        Args:
            source_type: Source type to clear.
        """
        source_dir = self.cache_dir / source_type
        if source_dir.exists():
            shutil.rmtree(source_dir)

    def clear_all(self) -> None:
        """Clear all cache entries."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self._ensure_cache_dir_exists()
