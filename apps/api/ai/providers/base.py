"""
The provider interface (Phase 8): one neutral form for a conversation with
tool calling, that each adapter translates to and from its wire format.

    system     instructions
    user       the person's question (or any user-turn text)
    assistant  the model's turn: text and/or tool calls; `raw` keeps the
               provider's own content blocks so they can be sent back
               unchanged (Anthropic requires this for thinking blocks)
    tool       a tool's result, answering `tool_call_id`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

STOP_REASONS = ("end", "tool_use", "max_tokens", "refusal")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # the tool's name, on tool messages
    is_error: bool = False
    raw: Any = None  # the provider's own assistant content, sent back as is


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ChatResult:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str  # one of STOP_REASONS
    usage: Usage
    model: str
    raw_assistant: Any = None

    def as_message(self) -> Message:
        return Message(role="assistant", content=self.text, tool_calls=list(self.tool_calls),
                       raw=self.raw_assistant)


class ProviderError(Exception):
    """A provider call failed. The message never contains credentials."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ProviderConfigError(ValueError):
    pass


class Provider(Protocol):
    name: str
    kind: str
    model: str
    external: bool

    async def chat(self, messages: list[Message], tools: list[ToolSpec], *, max_tokens: int = 4096,
                   model: str | None = None) -> ChatResult:
        ...


def retryable_status(status: int) -> bool:
    return status in (408, 409, 429) or status >= 500
