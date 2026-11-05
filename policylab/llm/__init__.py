"""Swappable LLM providers behind one interface.

``get_provider()`` returns the Anthropic provider when ANTHROPIC_API_KEY is set
(environment variable or Streamlit secret) and the deterministic offline
baseline otherwise. Tests always use the offline provider so CI needs no key.

The Streamlit app does not use the automatic choice: it asks for the offline
baseline unless ``live_mode_unlocked()`` confirms the viewer entered the
LIVE_MODE_PASSWORD secret.
"""

from __future__ import annotations

import os

from .base import LLMError, LLMProvider, LLMResponse, Task
from .config import live_mode_unlocked, setting
from .mock import MockProvider

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "MockProvider",
    "Task",
    "get_provider",
    "api_key",
    "live_mode_unlocked",
    "setting",
]


def api_key() -> str | None:
    return setting("ANTHROPIC_API_KEY")


def get_provider(name: str | None = None, model: str | None = None) -> LLMProvider:
    """name: 'anthropic', 'mock', or None (auto: anthropic if a key is available)."""
    name = name or os.environ.get("POLICYLAB_PROVIDER")
    if name == "mock" or (name is None and not api_key()):
        return MockProvider()
    from .anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=api_key(), model=model)
