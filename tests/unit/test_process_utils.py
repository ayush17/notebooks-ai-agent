"""Unit tests for process management utilities."""

import os
import time
from pathlib import Path

import pytest

from devassist.utils.process import (
    acquire_lock,
    is_process_running,
    read_pid_file,
    release_lock,
    write_pid_file,
)


class TestPIDFileOperations:
    """Tests for PID file operations."""

    def test_write_pid_file(self, tmp_path: Path) -> None:
        """Should write PID to file."""
        pid_file = tmp_path / "test.pid"
        pid = os.getpid()

        write_pid_file(pid_file, pid)

        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(pid)

    def test_write_pid_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        pid_file = tmp_path / "nested" / "dir" / "test.pid"
        pid = os.getpid()

        write_pid_file(pid_file, pid)

        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(pid)

    def test_write_pid_file_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing PID file."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        new_pid = os.getpid()
        write_pid_file(pid_file, new_pid)

        assert pid_file.read_text().strip() == str(new_pid)

    def test_read_pid_file(self, tmp_path: Path) -> None:
        """Should read PID from file."""
        pid_file = tmp_path / "test.pid"
        expected_pid = 12345
        pid_file.write_text(str(expected_pid))

        pid = read_pid_file(pid_file)

        assert pid == expected_pid

    def test_read_pid_file_nonexistent(self, tmp_path: Path) -> None:
        """Should return None if file doesn't exist."""
        pid_file = tmp_path / "nonexistent.pid"

        pid = read_pid_file(pid_file)

        assert pid is None

    def test_read_pid_file_invalid_content(self, tmp_path: Path) -> None:
        """Should return None if content is not a valid PID."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("not-a-number")

        pid = read_pid_file(pid_file)

        assert pid is None

    def test_read_pid_file_empty(self, tmp_path: Path) -> None:
        """Should return None if file is empty."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("")

        pid = read_pid_file(pid_file)

        assert pid is None


class TestProcessRunning:
    """Tests for process running checks."""

    def test_is_process_running_current_process(self) -> None:
        """Should return True for current process."""
        current_pid = os.getpid()

        result = is_process_running(current_pid)

        assert result is True

    def test_is_process_running_nonexistent(self) -> None:
        """Should return False for nonexistent process."""
        # Use a very high PID unlikely to exist
        fake_pid = 99999999

        result = is_process_running(fake_pid)

        assert result is False

    def test_is_process_running_parent_process(self) -> None:
        """Should return True for parent process."""
        # Use parent process PID which we know is running
        parent_pid = os.getppid()

        result = is_process_running(parent_pid)

        assert result is True


class TestLockFileOperations:
    """Tests for lock file operations."""

    def test_acquire_lock_success(self, tmp_path: Path) -> None:
        """Should successfully acquire lock."""
        lock_file = tmp_path / "test.lock"

        result = acquire_lock(lock_file)

        assert result is True
        assert lock_file.exists()

    def test_acquire_lock_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Should create parent directories for lock file."""
        lock_file = tmp_path / "nested" / "dir" / "test.lock"

        result = acquire_lock(lock_file)

        assert result is True
        assert lock_file.exists()

    def test_acquire_lock_fails_when_locked(self, tmp_path: Path) -> None:
        """Should fail to acquire lock when already locked."""
        lock_file = tmp_path / "test.lock"

        # First lock should succeed
        assert acquire_lock(lock_file) is True

        # Second lock should fail
        assert acquire_lock(lock_file) is False

    def test_acquire_lock_succeeds_after_release(self, tmp_path: Path) -> None:
        """Should succeed after lock is released."""
        lock_file = tmp_path / "test.lock"

        # Acquire and release
        assert acquire_lock(lock_file) is True
        release_lock(lock_file)

        # Should be able to acquire again
        assert acquire_lock(lock_file) is True

    def test_acquire_lock_with_timeout(self, tmp_path: Path) -> None:
        """Should timeout if lock cannot be acquired."""
        lock_file = tmp_path / "test.lock"

        # First lock succeeds
        assert acquire_lock(lock_file) is True

        # Second lock with timeout should fail after timeout
        start_time = time.time()
        result = acquire_lock(lock_file, timeout=1.0)
        elapsed = time.time() - start_time

        assert result is False
        assert elapsed >= 1.0
        assert elapsed < 2.0  # Should not take much longer than timeout

    def test_acquire_lock_stale_detection(self, tmp_path: Path) -> None:
        """Should detect and remove stale locks."""
        lock_file = tmp_path / "test.lock"

        # Create a lock file with a dead process PID
        lock_data = {"pid": 99999999, "timestamp": time.time() - 3600}
        import json
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps(lock_data))

        # Should successfully acquire by removing stale lock
        result = acquire_lock(lock_file)

        assert result is True

    def test_release_lock(self, tmp_path: Path) -> None:
        """Should release lock and remove file."""
        lock_file = tmp_path / "test.lock"

        acquire_lock(lock_file)
        release_lock(lock_file)

        assert not lock_file.exists()

    def test_release_lock_nonexistent(self, tmp_path: Path) -> None:
        """Should handle releasing nonexistent lock gracefully."""
        lock_file = tmp_path / "nonexistent.lock"

        # Should not raise an error
        release_lock(lock_file)

    def test_lock_contains_pid(self, tmp_path: Path) -> None:
        """Lock file should contain current process PID."""
        lock_file = tmp_path / "test.lock"

        acquire_lock(lock_file)

        import json
        lock_data = json.loads(lock_file.read_text())
        assert lock_data["pid"] == os.getpid()
        assert "timestamp" in lock_data

    def test_acquire_lock_retries(self, tmp_path: Path) -> None:
        """Should retry if lock is released during timeout."""
        lock_file = tmp_path / "test.lock"

        # Acquire initial lock
        assert acquire_lock(lock_file) is True

        # Start acquisition in background (this would normally be another process)
        import threading

        def release_after_delay():
            time.sleep(0.5)
            release_lock(lock_file)

        thread = threading.Thread(target=release_after_delay)
        thread.start()

        # Try to acquire with timeout - should succeed after lock is released
        start_time = time.time()
        result = acquire_lock(lock_file, timeout=2.0)
        elapsed = time.time() - start_time

        thread.join()

        assert result is True
        assert elapsed >= 0.5  # Should have waited for release
        assert elapsed < 2.0  # But not the full timeout
