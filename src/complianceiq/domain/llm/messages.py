"""Chat message value objects.

These are the *provider-agnostic* representation of a conversation. No Anthropic
or OpenAI types ever appear in the domain; adapters translate to/from these.

The distinction between roles matters for safety: ``system`` messages are our
trusted instructions, while ``user`` (and, later, retrieved-context) content is
**untrusted** and must be scanned for prompt-injection before it reaches a model
(see :mod:`complianceiq.domain.policies.prompt_safety`).
"""

from __future__ import annotations

from enum import StrEnum

from complianceiq.domain._base import FrozenModel


class MessageRole(StrEnum):
    """Who authored a message.

    - ``SYSTEM``: our trusted instructions (highest authority).
    - ``USER``: the end-user's input (untrusted).
    - ``ASSISTANT``: a prior model response (untrusted for injection purposes).
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

    @property
    def is_trusted(self) -> bool:
        """Whether content in this role originates from us (the system)."""
        return self is MessageRole.SYSTEM


class LLMMessage(FrozenModel):
    """A single message in a conversation.

    Attributes:
        role: Who authored the message.
        content: The message text. May be empty for an assistant turn that only
            carried tool calls (not used in Phase 2, but allowed by the contract).
    """

    role: MessageRole
    content: str

    @classmethod
    def system(cls, content: str) -> LLMMessage:
        """Convenience constructor for a trusted system instruction."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> LLMMessage:
        """Convenience constructor for an untrusted user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> LLMMessage:
        """Convenience constructor for a prior assistant message."""
        return cls(role=MessageRole.ASSISTANT, content=content)
