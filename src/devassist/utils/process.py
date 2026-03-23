"""Process management utilities for DevAssist.

Provides utilities for PID files, lock files, and process management.
"""

import json
import os
import time
from pathlib import Path


def write_pid_file(pid_file: Path, pid: int) -> None:
    """Write process ID to PID file.

    Creates parent directories if they don't exist.

    Args:
        pid_file: Path to PID file.
        pid: Process ID to write.
    """
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def read_pid_file(pid_file: Path) -> int | None:
    """Read process ID from PID file.

    Args:
        pid_file: Path to PID file.

    Returns:
        Process ID if valid, None otherwise.
    """
    if not pid_file.exists():
        return None

    try:
        content = pid_file.read_text().strip()
        if not content:
            return None
        return int(content)
    except (ValueError, OSError):
        return None


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running.

    Args:
        pid: Process ID to check.

    Returns:
        True if process is running, False otherwise.
    """
    try:
        # Send signal 0 to check if process exists
        # This doesn't actually send a signal, just checks permissions
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(lock_file: Path, timeout: float = 0.0) -> bool:
    """Acquire a lock file.

    Creates a lock file containing the current process PID and timestamp.
    If a lock already exists, checks if it's stale (process not running).

    Args:
        lock_file: Path to lock file.
        timeout: Maximum time to wait for lock (seconds). 0 means no wait.

    Returns:
        True if lock was acquired, False otherwise.
    """
    start_time = time.time()
    retry_interval = 0.1  # Check every 100ms

    while True:
        # Try to acquire the lock
        if _try_acquire_lock(lock_file):
            return True

        # Check timeout
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            return False

        # Wait before retry
        time.sleep(retry_interval)


def _try_acquire_lock(lock_file: Path) -> bool:
    """Attempt to acquire lock once.

    Args:
        lock_file: Path to lock file.

    Returns:
        True if lock was acquired, False if already locked.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if lock file exists
    if lock_file.exists():
        # Try to read lock data
        try:
            lock_data = json.loads(lock_file.read_text())
            locked_pid = lock_data.get("pid")

            # Check if the process holding the lock is still running
            if locked_pid and is_process_running(locked_pid):
                # Lock is held by a running process
                return False
            else:
                # Stale lock - remove it
                lock_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, OSError):
            # Corrupted lock file - remove it
            lock_file.unlink(missing_ok=True)

    # Create the lock file
    lock_data = {
        "pid": os.getpid(),
        "timestamp": time.time(),
    }
    try:
        lock_file.write_text(json.dumps(lock_data))
        return True
    except OSError:
        return False


def release_lock(lock_file: Path) -> None:
    """Release a lock file.

    Args:
        lock_file: Path to lock file.
    """
    lock_file.unlink(missing_ok=True)
