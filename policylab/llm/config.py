"""Settings read from the environment or, inside Streamlit, from ``st.secrets``.

Environment variables win so local runs and CI behave the same way with or
without a secrets file. On Streamlit Community Cloud, values pasted under
**Settings -> Secrets** are read through ``st.secrets``.
"""

from __future__ import annotations

import hmac
import os


def setting(name: str) -> str | None:
    """Return a non-empty setting from the environment or Streamlit secrets, else None."""
    value = os.environ.get(name)
    if value:
        return value
    try:  # Streamlit secrets, when running inside Streamlit with a secrets file
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value) if value else None


def live_mode_unlocked(entered_password: str | None) -> bool:
    """True only when an API key and LIVE_MODE_PASSWORD are configured and the password matches.

    The public app stays in demo mode unless the operator has set both secrets
    and the viewer types the password. A missing password secret keeps live
    mode off even when a key is present, so a deployed key is never usable by
    anonymous visitors.
    """
    if os.environ.get("POLICYLAB_PROVIDER") == "mock":
        return False
    expected = setting("LIVE_MODE_PASSWORD")
    if not (setting("ANTHROPIC_API_KEY") and expected and entered_password):
        return False
    return hmac.compare_digest(entered_password.encode(), expected.encode())
