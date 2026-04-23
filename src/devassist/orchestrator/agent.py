"""Orchestration Agent for DevAssist.

The main agent that coordinates between user requests, LLM, and MCP tools.
"""

from dataclasses import dataclass, field
from typing import Any

from devassist.mcp.client import MCPClient, ToolResult, ToolSchema
from devassist.mcp.registry import MCPRegistry
from devassist.orchestrator.llm_client import LLMClient, LLMResponse, Message, ToolCall
from devassist.orchestrator.native_jira_tools import build_jira_native_tool_schemas, run_jira_native_tool
from devassist.orchestrator.prompts import get_system_prompt, build_tool_context


@dataclass
class AgentResponse:
    """Response from the orchestration agent.

    Attributes:
        content: The final response text
        sources_used: List of MCP servers that were queried
        tool_calls_made: Number of tool calls made
        error: Error message if something went wrong
    """

    content: str
    sources_used: list[str] = field(default_factory=list)
    tool_calls_made: int = 0
    error: str | None = None


class OrchestrationAgent:
    """Main orchestration agent that coordinates LLM and MCP tools.

    This agent:
    1. Receives user prompts
    2. Builds context with available MCP tools
    3. Sends to LLM for processing
    4. Executes any tool calls via MCP
    5. Returns the final response
    """

    MAX_ITERATIONS = 10  # Prevent infinite loops

    def __init__(
        self,
        llm_client: LLMClient,
        mcp_client: MCPClient,
        registry: MCPRegistry | None = None,
    ) -> None:
        """Initialize the orchestration agent.

        Args:
            llm_client: Client for LLM interactions.
            mcp_client: Client for MCP tool execution.
            registry: Registry of available MCP servers.
        """
        self._llm = llm_client
        self._mcp = mcp_client
        self._registry = registry or MCPRegistry()

    async def process(self, user_prompt: str) -> AgentResponse:
        """Process a user prompt through the orchestration pipeline.

        Args:
            user_prompt: The user's request in natural language.

        Returns:
            AgentResponse with the final response and metadata.
        """
        # Track state
        sources_used: set[str] = set()
        tool_calls_made = 0

        # Native Jira REST tools (API token) + MCP tools
        native_tools = build_jira_native_tool_schemas()
        tools = native_tools + self._mcp.get_all_tools()

        # Build initial messages
        system_prompt = self._build_system_prompt(tools)
        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        # Agentic loop
        for iteration in range(self.MAX_ITERATIONS):
            try:
                # Call LLM
                response = await self._llm.chat(messages, tools)

                # If no tool calls, we're done
                if not response.tool_calls:
                    return AgentResponse(
                        content=response.content,
                        sources_used=list(sources_used),
                        tool_calls_made=tool_calls_made,
                    )

                # Execute tool calls
                tool_results = await self._execute_tool_calls(response.tool_calls)
                tool_calls_made += len(response.tool_calls)

                # Track which sources were used
                for result in tool_results:
                    sources_used.add(result.server)

                # Add assistant message with tool calls
                messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                # Add tool results
                for i, result in enumerate(tool_results):
                    tool_call = response.tool_calls[i]
                    messages.append(
                        Message(
                            role="tool",
                            content=result.content if not result.is_error else f"Error: {result.content}",
                            tool_call_id=tool_call.id,
                        )
                    )

            except Exception as e:
                return AgentResponse(
                    content=f"An error occurred: {e}",
                    sources_used=list(sources_used),
                    tool_calls_made=tool_calls_made,
                    error=str(e),
                )

        # Max iterations reached
        return AgentResponse(
            content="I reached the maximum number of steps. Here's what I found so far.",
            sources_used=list(sources_used),
            tool_calls_made=tool_calls_made,
            error="Max iterations reached",
        )

    async def _execute_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolResult]:
        """Execute a list of tool calls.

        Args:
            tool_calls: Tool calls to execute.

        Returns:
            List of tool results.
        """
        results: list[ToolResult] = []
        for tc in tool_calls:
            native = await run_jira_native_tool(tc.name, tc.arguments)
            if native is not None:
                results.append(native)
            else:
                results.append(await self._mcp.call_tool(tc.name, tc.arguments))
        return results

    def _build_system_prompt(self, tools: list[ToolSchema]) -> str:
        """Build the system prompt with tool context.

        Args:
            tools: Available tools.

        Returns:
            Complete system prompt.
        """
        tool_formats = [t.to_llm_format() for t in tools]
        tool_context = build_tool_context(tool_formats)

        return f"{get_system_prompt()}\n\n{tool_context}"


async def create_agent(
    llm_provider: str = "vertex",
    project_id: str | None = None,
    api_key: str | None = None,
) -> tuple[OrchestrationAgent, MCPClient, MCPRegistry]:
    """Factory function to create an orchestration agent.

    Args:
        llm_provider: Which LLM to use ("vertex" or "anthropic").
        project_id: GCP project ID (for Vertex AI).
        api_key: API key (for Anthropic).

    Returns:
        Tuple of (agent, mcp_client, registry) - caller manages MCP connections.
    """
    from devassist.orchestrator.llm_client import AnthropicLLMClient, VertexAILLMClient

    # Create LLM client
    if llm_provider == "anthropic":
        llm_client: LLMClient = AnthropicLLMClient(api_key=api_key)
    else:
        llm_client = VertexAILLMClient(project_id=project_id)

    # Create MCP components
    mcp_client = MCPClient()
    registry = MCPRegistry()

    # Create agent
    agent = OrchestrationAgent(
        llm_client=llm_client,
        mcp_client=mcp_client,
        registry=registry,
    )

    return agent, mcp_client, registry
