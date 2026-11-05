"""Swappable LLM providers behind one interface.

``get_provider()`` returns the Anthropic provider when ANTHROPIC_API_KEY is set
(environment variable or Streamlit secret) and the deterministic offline
baseline otherwise. Tests always use the offline provider so CI needs no key.
"""

from __future__ import annotations

import os

from .base import LLMError, LLMProvider, LLMResponse, Task
from .mock import MockProvider

__all__ = ["LLMError", "LLMProvider", "LLMResponse", "MockProvider", "Task", "get_provider", "api_key"]


def api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:  # Streamlit secrets, when running inside Streamlit
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")  # type: ignore[no-any-return]
    except Exception:
        return None


def get_provider(name: str | None = None, model: str | None = None) -> LLMProvider:
    """name: 'anthropic', 'mock', or None (auto: anthropic if a key is available)."""
    name = name or os.environ.get("POLICYLAB_PROVIDER")
    if name == "mock" or (name is None and not api_key()):
        return MockProvider()
    from .anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=api_key(), model=model)
