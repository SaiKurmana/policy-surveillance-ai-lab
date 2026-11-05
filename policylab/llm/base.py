from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when a provider cannot return a valid structured response."""


@dataclass
class Task:
    """What the caller is asking for.

    ``kind`` and ``payload`` let offline baselines (which cannot read prompts)
    produce a comparable answer. Real LLM providers use only the prompts.
    """

    kind: str  # "qa" | "coding"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    parsed: BaseModel
    raw_text: str
    provider: str
    model: str  # model requested
    served_model: str  # model that actually produced the output (may differ on fallback)
    stop_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str
    is_live_llm: bool

    def structured(
        self, *, system: str, user: str, output_model: type[T], task: Task
    ) -> LLMResponse: ...
