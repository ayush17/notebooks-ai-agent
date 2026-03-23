"""Unit tests for RunnerManager."""

import os
import signal
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from devassist.core.runner_manager import RunnerManager, RunnerStatus


class TestRunnerManager:
    """Tests for RunnerManager."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create temporary workspace directory."""
        workspace = tmp_path / ".devassist"
        workspace.mkdir()
        return workspace

    @pytest.fixture
    def manager(self, workspace: Path) -> RunnerManager:
        """Create RunnerManager for testing."""
        return RunnerManager(workspace_dir=workspace)

    def test_init_creates_directories(self, workspace: Path) -> None:
        """Should create necessary directories."""
        manager = RunnerManager(workspace_dir=workspace)

        assert manager.workspace_dir == workspace
        assert manager.pid_file == workspace / "runner.pid"
        assert manager.lock_file == workspace / "runner.lock"
        assert (workspace / "logs").exists()

    def test_is_running_when_not_running(self, manager: RunnerManager) -> None:
        """Should return False when runner is not running."""
        result = manager.is_running()

        assert result is False

    def test_is_running_when_pid_file_exists_but_process_dead(
        self, manager: RunnerManager
    ) -> None:
        """Should return False when PID file exists but process is dead."""
        # Write a PID that doesn't exist
        manager.pid_file.write_text("99999999")

        result = manager.is_running()

        assert result is False
        # Should clean up stale PID file
        assert not manager.pid_file.exists()

    def test_is_running_when_actually_running(self, manager: RunnerManager) -> None:
        """Should return True when runner is actually running."""
        # Write current process PID (we know it's running)
        manager.pid_file.write_text(str(os.getpid()))

        result = manager.is_running()

        assert result is True

    def test_get_status_when_not_running(self, manager: RunnerManager) -> None:
        """Should return NOT_RUNNING status."""
        status = manager.get_status()

        assert status.status == "not_running"
        assert status.pid is None

    def test_get_status_when_running(self, manager: RunnerManager) -> None:
        """Should return RUNNING status with PID."""
        # Simulate running process
        current_pid = os.getpid()
        manager.pid_file.write_text(str(current_pid))

        status = manager.get_status()

        assert status.status == "running"
        assert status.pid == current_pid

    @patch("devassist.core.runner_manager.multiprocessing.Process")
    def test_start_creates_background_process(
        self, mock_process_class: Mock, manager: RunnerManager
    ) -> None:
        """Should create and start background process."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process_class.return_value = mock_process

        def mock_target():
            pass

        manager.start(target=mock_target)

        # Should create process
        mock_process_class.assert_called_once()
        # Should start process
        mock_process.start.assert_called_once()
        # Should write PID file
        assert manager.pid_file.exists()
        assert manager.pid_file.read_text().strip() == "12345"

    @patch("devassist.core.runner_manager.multiprocessing.Process")
    def test_start_acquires_lock(
        self, mock_process_class: Mock, manager: RunnerManager
    ) -> None:
        """Should acquire lock before starting."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process_class.return_value = mock_process

        def mock_target():
            pass

        manager.start(target=mock_target)

        # Lock file should exist
        assert manager.lock_file.exists()

    @patch("devassist.core.runner_manager.multiprocessing.Process")
    def test_start_fails_if_already_running(
        self, mock_process_class: Mock, manager: RunnerManager
    ) -> None:
        """Should raise error if runner is already running."""
        # Simulate already running
        manager.pid_file.write_text(str(os.getpid()))

        def mock_target():
            pass

        with pytest.raises(RuntimeError, match="already running"):
            manager.start(target=mock_target)

        # Should not create new process
        mock_process_class.assert_not_called()

    @patch("devassist.core.runner_manager.multiprocessing.Process")
    def test_start_fails_if_cannot_acquire_lock(
        self, mock_process_class: Mock, manager: RunnerManager
    ) -> None:
        """Should raise error if cannot acquire lock."""
        # Manually acquire the lock
        from devassist.utils.process import acquire_lock

        acquire_lock(manager.lock_file)

        def mock_target():
            pass

        with pytest.raises(RuntimeError, match="acquire lock"):
            manager.start(target=mock_target)

        mock_process_class.assert_not_called()

    def test_stop_when_not_running(self, manager: RunnerManager) -> None:
        """Should handle stop when not running gracefully."""
        # Should not raise an error
        manager.stop()

    def test_stop_sends_sigterm(self, manager: RunnerManager) -> None:
        """Should send SIGTERM to running process."""
        # Write PID file
        test_pid = 12345
        manager.pid_file.write_text(str(test_pid))

        with patch("os.kill") as mock_kill:
            with patch("devassist.core.runner_manager.is_process_running") as mock_running:
                # Simulate process running initially, then exits after SIGTERM
                mock_running.side_effect = [True, False]

                manager.stop()

                # Should have sent SIGTERM
                calls = mock_kill.call_args_list
                assert len(calls) >= 1
                assert calls[0] == ((test_pid, signal.SIGTERM),)

    def test_stop_cleans_up_files(self, manager: RunnerManager) -> None:
        """Should clean up PID and lock files."""
        # Create files
        manager.pid_file.write_text("12345")
        from devassist.utils.process import acquire_lock

        acquire_lock(manager.lock_file)

        with patch("os.kill"):
            # Mock kill so we don't try to signal nonexistent process
            manager.stop()

        # Files should be removed
        assert not manager.pid_file.exists()
        assert not manager.lock_file.exists()

    def test_stop_with_force(self, manager: RunnerManager) -> None:
        """Should send SIGKILL when force=True."""
        test_pid = os.getpid()
        manager.pid_file.write_text(str(test_pid))

        with patch("os.kill") as mock_kill:
            manager.stop(force=True)

            # Should send SIGKILL
            mock_kill.assert_called_with(test_pid, signal.SIGKILL)

    def test_stop_waits_for_graceful_shutdown(self, manager: RunnerManager) -> None:
        """Should wait for process to exit before forcing."""
        test_pid = 99999999  # Non-existent process
        manager.pid_file.write_text(str(test_pid))

        with patch("os.kill") as mock_kill:
            with patch("devassist.core.runner_manager.is_process_running") as mock_running:
                # Simulate process initially running, then exits quickly
                mock_running.side_effect = [True, False]

                start_time = time.time()
                manager.stop(timeout=2.0)
                elapsed = time.time() - start_time

                # Should return quickly since process exits after first check
                assert elapsed < 1.0
                # Should have tried SIGTERM
                assert mock_kill.call_count >= 1

    def test_get_log_path(self, manager: RunnerManager) -> None:
        """Should return path to log file."""
        log_path = manager.get_log_path()

        assert log_path == manager.workspace_dir / "logs" / "runner.log"


class TestRunnerStatus:
    """Tests for RunnerStatus model."""

    def test_create_not_running(self) -> None:
        """Should create NOT_RUNNING status."""
        status = RunnerStatus(status="not_running", pid=None)

        assert status.status == "not_running"
        assert status.pid is None

    def test_create_running(self) -> None:
        """Should create RUNNING status with PID."""
        status = RunnerStatus(status="running", pid=12345)

        assert status.status == "running"
        assert status.pid == 12345

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        status = RunnerStatus(status="running", pid=12345)

        result = status.to_dict()

        assert result == {"status": "running", "pid": 12345}
