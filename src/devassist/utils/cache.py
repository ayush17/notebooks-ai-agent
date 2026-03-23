"""Cache utility functions for DevAssist.

Pure functions for caching data to disk with TTL support.
Replaces the CacheManager class with simpler utility functions.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 900  # 15 minutes


def get_cached(
    key: str,
    cache_dir: Path,
    source_type: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Any | None:
    """Get cached data if not expired.

    Args:
        key: Cache key (will be hashed for filename)
        cache_dir: Base cache directory
        source_type: Optional source type for subdirectory organization
        ttl_seconds: Time-to-live in seconds

    Returns:
        Cached data if found and not expired, None otherwise
    """
    cache_path = _get_cache_path(key, cache_dir, source_type)

    if not cache_path.exists():
        logger.debug(f"Cache miss: {key} (file not found)")
        return None

    try:
        with open(cache_path) as f:
            cached = json.load(f)

        # Check if expired
        expires_at = datetime.fromisoformat(cached["expires_at"])
        if datetime.now() > expires_at:
            logger.debug(f"Cache expired: {key}")
            cache_path.unlink(missing_ok=True)
            return None

        logger.debug(f"Cache hit: {key}")
        return cached["data"]

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Corrupted cache file {cache_path}: {e}")
        cache_path.unlink(missing_ok=True)
        return None
    except Exception as e:
        logger.error(f"Failed to read cache {cache_path}: {e}")
        return None


def set_cached(
    key: str,
    data: Any,
    cache_dir: Path,
    source_type: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Store data in cache with expiration.

    Args:
        key: Cache key (will be hashed for filename)
        data: Data to cache (must be JSON serializable)
        cache_dir: Base cache directory
        source_type: Optional source type for subdirectory organization
        ttl_seconds: Time-to-live in seconds
    """
    cache_path = _get_cache_path(key, cache_dir, source_type)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_entry = {
        "key": key,
        "data": data,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
        "source_type": source_type,
    }

    try:
        with open(cache_path, "w") as f:
            json.dump(cache_entry, f, indent=2, default=str)
        logger.debug(f"Cached: {key} (expires in {ttl_seconds}s)")
    except Exception as e:
        logger.error(f"Failed to write cache {cache_path}: {e}")


def clear_cache(
    cache_dir: Path,
    source_type: str | None = None,
    older_than_seconds: int | None = None,
) -> int:
    """Clear cached data.

    Args:
        cache_dir: Base cache directory
        source_type: Optional source type to clear (None = all)
        older_than_seconds: Optional age threshold (None = all)

    Returns:
        Number of files cleared
    """
    if source_type:
        target_dir = cache_dir / source_type
    else:
        target_dir = cache_dir

    if not target_dir.exists():
        return 0

    cleared = 0
    cutoff_time = None
    if older_than_seconds:
        cutoff_time = datetime.now() - timedelta(seconds=older_than_seconds)

    try:
        for cache_file in target_dir.rglob("*.json"):
            should_clear = True

            if cutoff_time:
                # Check file modification time
                file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                should_clear = file_mtime < cutoff_time

            if should_clear:
                cache_file.unlink(missing_ok=True)
                cleared += 1

        logger.info(f"Cleared {cleared} cache files from {target_dir}")
        return cleared

    except Exception as e:
        logger.error(f"Failed to clear cache {target_dir}: {e}")
        return 0


def cleanup_expired_cache(cache_dir: Path) -> int:
    """Remove expired cache entries.

    Args:
        cache_dir: Base cache directory

    Returns:
        Number of expired entries removed
    """
    if not cache_dir.exists():
        return 0

    cleaned = 0
    current_time = datetime.now()

    try:
        for cache_file in cache_dir.rglob("*.json"):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)

                expires_at = datetime.fromisoformat(cached["expires_at"])
                if current_time > expires_at:
                    cache_file.unlink(missing_ok=True)
                    cleaned += 1

            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted or malformed cache file
                cache_file.unlink(missing_ok=True)
                cleaned += 1
            except Exception as e:
                logger.warning(f"Error checking cache file {cache_file}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired cache entries")
        return cleaned

    except Exception as e:
        logger.error(f"Failed to cleanup cache {cache_dir}: {e}")
        return 0


def get_cache_stats(cache_dir: Path) -> dict[str, Any]:
    """Get cache statistics.

    Args:
        cache_dir: Base cache directory

    Returns:
        Dictionary with cache statistics
    """
    if not cache_dir.exists():
        return {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_source": {},
            "expired_files": 0,
        }

    stats = {
        "total_files": 0,
        "total_size_bytes": 0,
        "by_source": {},
        "expired_files": 0,
    }

    current_time = datetime.now()

    try:
        for cache_file in cache_dir.rglob("*.json"):
            try:
                file_size = cache_file.stat().st_size
                stats["total_files"] += 1
                stats["total_size_bytes"] += file_size

                # Determine source type from path
                relative_path = cache_file.relative_to(cache_dir)
                if len(relative_path.parts) > 1:
                    source_type = relative_path.parts[0]
                    if source_type not in stats["by_source"]:
                        stats["by_source"][source_type] = {"files": 0, "size_bytes": 0}
                    stats["by_source"][source_type]["files"] += 1
                    stats["by_source"][source_type]["size_bytes"] += file_size

                # Check if expired
                try:
                    with open(cache_file) as f:
                        cached = json.load(f)
                    expires_at = datetime.fromisoformat(cached["expires_at"])
                    if current_time > expires_at:
                        stats["expired_files"] += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    stats["expired_files"] += 1

            except Exception as e:
                logger.debug(f"Error getting stats for {cache_file}: {e}")

    except Exception as e:
        logger.error(f"Failed to get cache stats {cache_dir}: {e}")

    return stats


def _get_cache_path(key: str, cache_dir: Path, source_type: str | None = None) -> Path:
    """Get cache file path for a key.

    Args:
        key: Cache key
        cache_dir: Base cache directory
        source_type: Optional source type for subdirectory

    Returns:
        Path to cache file
    """
    # Hash the key to create a safe filename
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]

    if source_type:
        return cache_dir / source_type / f"{key_hash}.json"
    else:
        return cache_dir / f"{key_hash}.json"


def invalidate_cache_key(
    key: str,
    cache_dir: Path,
    source_type: str | None = None,
) -> bool:
    """Invalidate a specific cache key.

    Args:
        key: Cache key to invalidate
        cache_dir: Base cache directory
        source_type: Optional source type

    Returns:
        True if cache was invalidated, False if not found
    """
    cache_path = _get_cache_path(key, cache_dir, source_type)

    if cache_path.exists():
        try:
            cache_path.unlink()
            logger.debug(f"Invalidated cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache {cache_path}: {e}")
            return False

    return False


def is_cached(
    key: str,
    cache_dir: Path,
    source_type: str | None = None,
) -> bool:
    """Check if a key is cached and not expired.

    Args:
        key: Cache key to check
        cache_dir: Base cache directory
        source_type: Optional source type

    Returns:
        True if key is cached and valid, False otherwise
    """
    return get_cached(key, cache_dir, source_type) is not None