"""Anthropic Claude provider (structured outputs validated by pydantic)."""

from __future__ import annotations

from .base import LLMError, LLMResponse, T, Task
from .config import setting

# Override with the POLICYLAB_MODEL environment variable or Streamlit secret.
DEFAULT_MODEL = "claude-sonnet-5-5"


class AnthropicProvider:
    name = "anthropic"
    is_live_llm = True

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int = 16000,
        client=None,
    ):
        self.model = model or setting("POLICYLAB_MODEL") or DEFAULT_MODEL
        self.effort = effort or setting("POLICYLAB_EFFORT") or "medium"
        self.max_tokens = max_tokens
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.client = client

    def structured(
        self, *, system: str, user: str, output_model: type[T], task: Task
    ) -> LLMResponse:
        import anthropic

        schema = anthropic.transform_schema(output_model)
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                # If a safety classifier declines, let the API retry on its
                # recommended fallback model instead of failing the request.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise LLMError(f"Rate limited by the Anthropic API: {e}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Could not reach the Anthropic API: {e}") from e

        if resp.stop_reason == "refusal":
            raise LLMError("The model declined this request (stop_reason=refusal).")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Output was truncated (max_tokens); not using a partial answer.")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        try:
            parsed = output_model.model_validate_json(text)
        except Exception as e:  # pydantic.ValidationError or JSON error
            raise LLMError(f"Model output failed schema validation: {e}") from e
        usage = {}
        if getattr(resp, "usage", None) is not None:
            usage = {
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
            }
        return LLMResponse(
            parsed=parsed,
            raw_text=text,
            provider=self.name,
            model=self.model,
            served_model=getattr(resp, "model", self.model) or self.model,
            stop_reason=resp.stop_reason or "",
            usage=usage,
        )
