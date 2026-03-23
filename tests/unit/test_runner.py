"""Unit tests for Runner core logic."""

import asyncio
import signal
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from devassist.core.runner import Runner
from devassist.models.context import ContextItem, SourceType
from devassist.models.mcp_config import MCPConfig, RunnerConfig


class TestRunner:
    """Tests for Runner class."""

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        """Create temporary workspace directory."""
        workspace = tmp_path / ".devassist"
        workspace.mkdir()
        return workspace

    @pytest.fixture
    def mock_config(self, workspace: Path) -> MCPConfig:
        """Create mock MCP configuration."""
        return MCPConfig(
            version="1.0",
            ai={"provider": "claude", "claude": {"api_key": "sk-test"}},
            runner={
                "enabled": True,
                "interval_minutes": 1,
                "prompt": "Test prompt",
                "output_destination": str(workspace / "runner-output.md"),
            },
            sources={"gmail": {"enabled": True}},
        )

    @pytest.fixture
    def mock_ai_client(self):
        """Create mock AI client."""
        client = AsyncMock()
        client.execute_prompt = AsyncMock(return_value="AI response")
        return client

    @pytest.fixture
    def mock_aggregator(self):
        """Create mock context aggregator."""
        aggregator = AsyncMock()
        aggregator.fetch_all = AsyncMock(return_value=[])
        return aggregator

    @pytest.fixture
    def runner(
        self, workspace: Path, mock_config: MCPConfig, mock_ai_client, mock_aggregator
    ) -> Runner:
        """Create Runner for testing."""
        return Runner(
            config=mock_config,
            workspace_dir=workspace,
            ai_client=mock_ai_client,
            aggregator=mock_aggregator,
        )

    def test_init(self, runner: Runner, workspace: Path) -> None:
        """Should initialize with correct configuration."""
        assert runner.workspace_dir == workspace
        assert runner.interval_minutes == 1
        assert runner.prompt == "Test prompt"
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_execute_once(
        self, runner: Runner, mock_ai_client, mock_aggregator
    ) -> None:
        """Should execute prompt once successfully."""
        # Setup
        items = [
            ContextItem(
                id="1",
                source_id="gmail_1",
                source_type=SourceType.GMAIL,
                title="Test email",
                timestamp=datetime.now(),
            )
        ]
        mock_aggregator.fetch_all = AsyncMock(return_value=items)
        mock_ai_client.execute_prompt = AsyncMock(return_value="AI summary")

        # Execute
        result = await runner.execute_once()

        # Verify
        assert result is not None
        assert "AI summary" in result
        mock_aggregator.fetch_all.assert_called_once()
        mock_ai_client.execute_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_once_with_empty_context(
        self, runner: Runner, mock_ai_client, mock_aggregator
    ) -> None:
        """Should handle empty context gracefully."""
        mock_aggregator.fetch_all = AsyncMock(return_value=[])
        mock_ai_client.execute_prompt = AsyncMock(return_value="No new items")

        result = await runner.execute_once()

        assert result is not None
        mock_ai_client.execute_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_once_writes_output(
        self, runner: Runner, workspace: Path, mock_ai_client
    ) -> None:
        """Should write output to destination file."""
        mock_ai_client.execute_prompt = AsyncMock(return_value="Test output")

        await runner.execute_once()

        # Output file should be created
        output_file = workspace / "runner-output.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert "Test output" in content

    @pytest.mark.asyncio
    async def test_execute_once_handles_errors(
        self, runner: Runner, mock_ai_client, mock_aggregator
    ) -> None:
        """Should handle execution errors gracefully."""
        mock_ai_client.execute_prompt = AsyncMock(
            side_effect=Exception("AI error")
        )

        # Should not raise, but return None
        result = await runner.execute_once()
        assert result is None

    @pytest.mark.asyncio
    async def test_run_executes_at_intervals(
        self, runner: Runner, mock_ai_client
    ) -> None:
        """Should execute at configured intervals."""
        mock_ai_client.execute_prompt = AsyncMock(return_value="Test")

        # Run for a short time - use 0.02 minutes (1.2 seconds) interval
        runner.interval_minutes = 0.02

        async def stop_after_executions():
            # Wait for at least 2 executions
            for _ in range(30):  # Wait up to 3 seconds
                await asyncio.sleep(0.1)
                if mock_ai_client.execute_prompt.call_count >= 2:
                    break
            runner.stop()

        # Run both tasks with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    runner.run(),
                    stop_after_executions(),
                ),
                timeout=5.0,  # 5 second max
            )
        except asyncio.TimeoutError:
            runner.stop()
            pytest.fail(f"Test timed out. Executions: {mock_ai_client.execute_prompt.call_count}")

        # Should have executed at least twice
        assert mock_ai_client.execute_prompt.call_count >= 2

    @pytest.mark.asyncio
    async def test_run_stops_on_signal(self, runner: Runner) -> None:
        """Should stop when stop() is called."""
        runner.interval_minutes = 1  # Long interval

        async def stop_immediately():
            await asyncio.sleep(0.01)
            runner.stop()

        # Should exit quickly without timing out
        start_time = asyncio.get_event_loop().time()

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    runner.run(),
                    stop_immediately(),
                ),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            runner.stop()
            pytest.fail("Test timed out - runner did not stop")

        elapsed = asyncio.get_event_loop().time() - start_time

        assert elapsed < 0.5  # Should exit quickly
        assert runner.running is False

    def test_stop_sets_running_flag(self, runner: Runner) -> None:
        """Should set running flag to False."""
        runner.running = True
        runner.stop()
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_updates_last_run_timestamp(
        self, runner: Runner, workspace: Path
    ) -> None:
        """Should update last run timestamp in config."""
        await runner.execute_once()

        # Should have updated timestamp
        assert runner.last_run is not None
        assert isinstance(runner.last_run, datetime)

    @pytest.mark.asyncio
    async def test_formats_context_for_ai(
        self, runner: Runner, mock_ai_client, mock_aggregator
    ) -> None:
        """Should format context items for AI prompt."""
        items = [
            ContextItem(
                id="1",
                source_id="gmail_1",
                source_type=SourceType.GMAIL,
                title="Email 1",
                timestamp=datetime.now(),
                relevance_score=0.9,
            ),
            ContextItem(
                id="2",
                source_id="slack_2",
                source_type=SourceType.SLACK,
                title="Message 2",
                timestamp=datetime.now(),
                relevance_score=0.7,
            ),
        ]
        mock_aggregator.fetch_all = AsyncMock(return_value=items)

        await runner.execute_once()

        # Verify AI was called with formatted context
        call_args = mock_ai_client.execute_prompt.call_args
        assert call_args is not None
        context = call_args[0][1]  # Second argument is context
        assert "items" in context
        assert len(context["items"]) == 2

    @pytest.mark.asyncio
    async def test_execute_once_with_no_ai_client(self, workspace: Path) -> None:
        """Should handle missing AI client gracefully."""
        config = MCPConfig(
            runner={"enabled": True, "prompt": "Test"}
        )
        runner = Runner(
            config=config,
            workspace_dir=workspace,
            ai_client=None,
            aggregator=AsyncMock(),
        )

        # Should not crash
        result = await runner.execute_once()
        assert result is None


class TestRunnerSignalHandling:
    """Tests for signal handling in Runner."""

    @pytest.mark.asyncio
    async def test_handles_sigterm(self) -> None:
        """Should handle SIGTERM gracefully."""
        config = MCPConfig(runner={"enabled": True})
        runner = Runner(
            config=config,
            ai_client=AsyncMock(),
            aggregator=AsyncMock(),
        )

        async def send_signal():
            await asyncio.sleep(0.01)
            # Simulate SIGTERM by calling stop
            runner.stop()

        # Should exit cleanly
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    runner.run(),
                    send_signal(),
                ),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            runner.stop()
            pytest.fail("Test timed out")

        assert runner.running is False

    @pytest.mark.asyncio
    async def test_handles_sigint(self) -> None:
        """Should handle SIGINT (Ctrl+C) gracefully."""
        config = MCPConfig(runner={"enabled": True})
        runner = Runner(
            config=config,
            ai_client=AsyncMock(),
            aggregator=AsyncMock(),
        )

        async def send_signal():
            await asyncio.sleep(0.01)
            runner.stop()

        # Should exit cleanly
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    runner.run(),
                    send_signal(),
                ),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            runner.stop()
            pytest.fail("Test timed out")

        assert runner.running is False
