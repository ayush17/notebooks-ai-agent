"""Unit tests for AI CLI commands."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from devassist.cli.ai import app
from devassist.models.mcp_config import MCPConfig


runner = CliRunner()


class TestAIRunCommand:
    """Tests for devassist ai run command."""

    @pytest.fixture
    def mock_config(self, tmp_path: Path) -> MCPConfig:
        """Create mock MCP configuration."""
        return MCPConfig(
            version="1.0",
            ai={"provider": "claude", "claude": {"api_key": "sk-test"}},
            runner={
                "enabled": True,
                "interval_minutes": 5,
                "prompt": "Test prompt",
                "output_destination": str(tmp_path / "output.md"),
            },
        )

    @patch("devassist.cli.ai.ConfigManager")
    @patch("devassist.cli.ai.RunnerManager")
    @patch("devassist.cli.ai.get_ai_client")
    def test_run_starts_background_process(
        self,
        mock_get_client: Mock,
        mock_runner_manager_class: Mock,
        mock_config_manager_class: Mock,
        mock_config: MCPConfig,
    ) -> None:
        """Should start background runner process."""
        # Setup mocks
        mock_config_manager = MagicMock()
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager

        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = False
        mock_runner_manager.get_status.return_value = Mock(status="running", pid=12345)
        mock_runner_manager.get_log_path.return_value = Path("/tmp/runner.log")
        mock_runner_manager_class.return_value = mock_runner_manager

        mock_get_client.return_value = MagicMock()

        # Run command
        result = runner.invoke(app, ["run"])

        # Verify
        assert result.exit_code == 0
        assert "Runner Started" in result.output or "started" in result.output.lower()
        mock_runner_manager.start.assert_called_once()

    @patch("devassist.cli.ai.ConfigManager")
    @patch("devassist.cli.ai.RunnerManager")
    def test_run_fails_if_already_running(
        self,
        mock_runner_manager_class: Mock,
        mock_config_manager_class: Mock,
        mock_config: MCPConfig,
    ) -> None:
        """Should fail if runner is already running."""
        mock_config_manager = MagicMock()
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager_class.return_value = mock_config_manager

        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = True
        mock_runner_manager.get_status.return_value = Mock(status="running", pid=12345)
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["run"])

        assert result.exit_code == 1
        assert "already running" in result.output

    @patch("devassist.cli.ai.ConfigManager")
    @patch("devassist.cli.ai.get_ai_client")
    def test_run_fails_without_api_key(
        self,
        mock_get_client: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """Should fail if API key is not configured."""
        config = MCPConfig(
            ai={"provider": "claude", "claude": {"api_key": None}},
        )

        mock_config_manager = MagicMock()
        mock_config_manager.load_config.return_value = config
        mock_config_manager_class.return_value = mock_config_manager

        mock_get_client.side_effect = RuntimeError("API key not configured")

        result = runner.invoke(app, ["run"])

        assert result.exit_code == 1
        assert "API key" in result.output or "Error" in result.output


class TestAIKillCommand:
    """Tests for devassist ai kill command."""

    @patch("devassist.cli.ai.RunnerManager")
    def test_kill_stops_running_process(
        self, mock_runner_manager_class: Mock
    ) -> None:
        """Should stop running process."""
        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = True
        mock_runner_manager.get_status.return_value = Mock(status="running", pid=12345)
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["kill"])

        assert result.exit_code == 0
        assert "stopped" in result.output.lower()
        mock_runner_manager.stop.assert_called_once_with(force=False)

    @patch("devassist.cli.ai.RunnerManager")
    def test_kill_with_force(self, mock_runner_manager_class: Mock) -> None:
        """Should force kill when --force is used."""
        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = True
        mock_runner_manager.get_status.return_value = Mock(status="running", pid=12345)
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["kill", "--force"])

        assert result.exit_code == 0
        mock_runner_manager.stop.assert_called_once_with(force=True)

    @patch("devassist.cli.ai.RunnerManager")
    def test_kill_when_not_running(self, mock_runner_manager_class: Mock) -> None:
        """Should handle case when runner is not running."""
        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = False
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["kill"])

        assert result.exit_code == 0
        assert "not" in result.output.lower() or "No runner" in result.output


class TestAIStatusCommand:
    """Tests for devassist ai status command."""

    @patch("devassist.cli.ai.ConfigManager")
    @patch("devassist.cli.ai.RunnerManager")
    def test_status_shows_running(
        self,
        mock_runner_manager_class: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """Should show running status with details."""
        config = MCPConfig(
            ai={"provider": "claude"},
            runner={"interval_minutes": 5, "prompt": "Test"},
        )

        mock_config_manager = MagicMock()
        mock_config_manager.load_config.return_value = config
        mock_config_manager_class.return_value = mock_config_manager

        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = True
        mock_runner_manager.get_status.return_value = Mock(status="running", pid=12345)
        mock_runner_manager.get_log_path.return_value = Path("/tmp/runner.log")
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Running" in result.output
        assert "12345" in result.output

    @patch("devassist.cli.ai.ConfigManager")
    @patch("devassist.cli.ai.RunnerManager")
    def test_status_shows_not_running(
        self,
        mock_runner_manager_class: Mock,
        mock_config_manager_class: Mock,
    ) -> None:
        """Should show not running status."""
        config = MCPConfig()

        mock_config_manager = MagicMock()
        mock_config_manager.load_config.return_value = config
        mock_config_manager_class.return_value = mock_config_manager

        mock_runner_manager = MagicMock()
        mock_runner_manager.is_running.return_value = False
        mock_runner_manager.get_status.return_value = Mock(status="not_running", pid=None)
        mock_runner_manager.get_log_path.return_value = Path("/tmp/runner.log")
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Not running" in result.output or "not_running" in result.output.lower()


class TestAILogsCommand:
    """Tests for devassist ai logs command."""

    @patch("devassist.cli.ai.RunnerManager")
    def test_logs_shows_content(
        self, mock_runner_manager_class: Mock, tmp_path: Path
    ) -> None:
        """Should show log file content."""
        log_file = tmp_path / "runner.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        mock_runner_manager = MagicMock()
        mock_runner_manager.get_log_path.return_value = log_file
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["logs"])

        assert result.exit_code == 0
        assert "Line 1" in result.output
        assert "Line 2" in result.output
        assert "Line 3" in result.output

    @patch("devassist.cli.ai.RunnerManager")
    def test_logs_handles_missing_file(
        self, mock_runner_manager_class: Mock, tmp_path: Path
    ) -> None:
        """Should handle missing log file gracefully."""
        mock_runner_manager = MagicMock()
        mock_runner_manager.get_log_path.return_value = tmp_path / "nonexistent.log"
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["logs"])

        assert result.exit_code == 0
        assert "No log file" in result.output or "not" in result.output.lower()

    @patch("devassist.cli.ai.RunnerManager")
    def test_logs_limits_lines(
        self, mock_runner_manager_class: Mock, tmp_path: Path
    ) -> None:
        """Should respect --lines option."""
        log_file = tmp_path / "runner.log"
        log_file.write_text("\n".join([f"Line {i}" for i in range(100)]))

        mock_runner_manager = MagicMock()
        mock_runner_manager.get_log_path.return_value = log_file
        mock_runner_manager_class.return_value = mock_runner_manager

        result = runner.invoke(app, ["logs", "--lines", "10"])

        assert result.exit_code == 0
        # Should show last 10 lines
        assert "Line 99" in result.output
        assert "Line 90" in result.output
        # Should not show earlier lines
        assert "Line 0" not in result.output
