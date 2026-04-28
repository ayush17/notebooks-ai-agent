"""LLM Client for the orchestration agent.

Provides a unified interface for interacting with LLMs that support tool calling.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from devassist.mcp.client import ToolSchema
from devassist.models.config import DEFAULT_VERTEX_GEMINI_MODEL, sanitize_gcp_field
from devassist.utils.gcp_env import resolve_gcp_project_id


@dataclass
class ToolCall:
    """Represents a tool call requested by the LLM.

    Attributes:
        id: Unique identifier for this tool call
        name: Name of the tool to call
        arguments: Arguments to pass to the tool
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """A message in the conversation.

    Attributes:
        role: Message role (system, user, assistant, tool)
        content: Message content
        tool_calls: Tool calls (for assistant messages)
        tool_call_id: ID of the tool call this responds to (for tool messages)
    """

    role: str
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    """Response from the LLM.

    Attributes:
        content: Text content of the response
        tool_calls: Tool calls requested by the LLM (if any)
        finish_reason: Why the response ended (stop, tool_calls, etc.)
    """

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send messages to the LLM and get a response.

        Args:
            messages: Conversation history.
            tools: Available tools the LLM can call.

        Returns:
            LLM response, possibly including tool calls.
        """
        ...


class VertexAILLMClient(LLMClient):
    """LLM client using Google Vertex AI (Gemini).
    
    Note: This client is for Gemini models. For Claude on Vertex AI,
    use AnthropicLLMClient with CLAUDE_CODE_USE_VERTEX=1.
    """

    DEFAULT_MODEL = DEFAULT_VERTEX_GEMINI_MODEL

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
        model: str | None = None,
    ) -> None:
        """Initialize Vertex AI client.

        Args:
            project_id: GCP project ID.
            location: GCP region.
            model: Model name.
        """
        pid = sanitize_gcp_field(project_id or "")
        self.project_id = sanitize_gcp_field(pid or resolve_gcp_project_id())
        self.location = sanitize_gcp_field(location)
        self.model = sanitize_gcp_field(model or self.DEFAULT_MODEL)
        self._client: Any = None
        self._genai = None
        self._types = None

    def _get_genai(self) -> Any:
        """Lazily import google.genai."""
        if self._genai is None:
            from google import genai
            self._genai = genai
        return self._genai

    def _get_types(self) -> Any:
        """Lazily import google.genai.types."""
        if self._types is None:
            from google.genai import types
            self._types = types
        return self._types

    def _get_client(self) -> Any:
        """Get or create the Vertex AI client."""
        try:
            genai = self._get_genai()

            if self._client is None:
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location,
                )
            return self._client
        except ImportError as e:
            raise RuntimeError(
                "Vertex AI not available. Run: pip install google-cloud-aiplatform"
            ) from e

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send messages to Gemini and get a response."""
        import asyncio

        types = self._get_types()
        client = self._get_client()

        # Convert messages to Gemini format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=msg.content)]))
            elif msg.role == "assistant":
                parts = []
                if msg.content:
                    parts.append(types.Part(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=tc.name, args=tc.arguments
                                )
                            )
                        )
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                # Tool results
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=msg.tool_call_id or "unknown",
                                    response={"result": msg.content},
                                )
                            )
                        ],
                    )
                )

        # Convert tools to Gemini format
        gemini_tools = None
        if tools:
            function_declarations = []
            for tool in tools:
                llm_format = tool.to_llm_format()
                func = llm_format["function"]
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=func["name"],
                        description=func["description"],
                        parameters=func.get("parameters"),
                    )
                )
            gemini_tools = [types.Tool(function_declarations=function_declarations)]

        # Make the API call
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
            tools=gemini_tools,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            ),
        )

        # Parse response
        content = ""
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content += part.text
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_calls.append(
                            ToolCall(
                                id=fc.name,  # Gemini doesn't have separate IDs
                                name=fc.name,
                                arguments=dict(fc.args) if fc.args else {},
                            )
                        )

        finish_reason = "tool_calls" if tool_calls else "stop"
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish_reason)


class AnthropicLLMClient(LLMClient):
    """LLM client using Anthropic Claude.
    
    Supports both direct Anthropic API and Claude on Vertex AI (Red Hat setup).
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    VERTEX_MODEL = "claude-sonnet-4@20250514"  # Vertex AI model format

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        use_vertex: bool | None = None,
        vertex_project_id: str | None = None,
        vertex_region: str | None = None,
    ) -> None:
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key (for direct API, uses ANTHROPIC_API_KEY env var).
            model: Model name.
            use_vertex: Use Claude on Vertex AI (auto-detected from CLAUDE_CODE_USE_VERTEX).
            vertex_project_id: GCP project ID (from ANTHROPIC_VERTEX_PROJECT_ID).
            vertex_region: GCP region (from CLOUD_ML_REGION).
        """
        import os
        
        self.api_key = api_key
        
        # Auto-detect Vertex AI mode from Red Hat environment
        self.use_vertex = use_vertex
        if self.use_vertex is None:
            self.use_vertex = os.environ.get("CLAUDE_CODE_USE_VERTEX") == "1"
        
        explicit = sanitize_gcp_field(vertex_project_id or "")
        self.vertex_project_id = sanitize_gcp_field(explicit or resolve_gcp_project_id())
        self.vertex_region = vertex_region or os.environ.get("CLOUD_ML_REGION", "us-east5")
        
        # Use appropriate model for the backend
        if model:
            self.model = sanitize_gcp_field(model)
        elif self.use_vertex:
            self.model = self.VERTEX_MODEL
        else:
            self.model = self.DEFAULT_MODEL
            
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        try:
            import anthropic

            if self._client is None:
                if self.use_vertex:
                    # Use Claude on Vertex AI (Red Hat setup)
                    from anthropic import AnthropicVertex
                    
                    if not self.vertex_project_id:
                        raise RuntimeError(
                            "GCP project ID not found for Claude on Vertex. Set "
                            "ANTHROPIC_VERTEX_PROJECT_ID or GOOGLE_CLOUD_PROJECT, or run "
                            "`gcloud config set project YOUR_PROJECT_ID` (the active gcloud "
                            "profile under ~/.config/gcloud is used as a fallback). "
                            "For credentials (often confused with 'project'), run "
                            "`gcloud auth application-default login` or set "
                            "GOOGLE_APPLICATION_CREDENTIALS to a service account JSON path."
                        )
                    
                    self._client = AnthropicVertex(
                        project_id=self.vertex_project_id,
                        region=self.vertex_region,
                    )
                else:
                    # Use direct Anthropic API
                    self._client = anthropic.Anthropic(api_key=self.api_key)
            return self._client
        except ImportError as e:
            raise RuntimeError(
                "Anthropic not available. Run: pip install anthropic"
            ) from e

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send messages to Claude and get a response."""
        import asyncio

        client = self._get_client()

        # Extract system message
        system = ""
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system = msg.content
            elif msg.role == "user":
                chat_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                chat_messages.append({"role": "assistant", "content": content})
            elif msg.role == "tool":
                chat_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                llm_format = tool.to_llm_format()
                func = llm_format["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })

        # Make the API call
        loop = asyncio.get_event_loop()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(**kwargs),
        )

        # Parse response
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        finish_reason = "tool_calls" if tool_calls else "stop"
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish_reason)
