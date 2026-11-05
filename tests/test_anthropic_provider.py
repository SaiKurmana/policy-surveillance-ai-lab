"""The Anthropic provider is tested against a fake client: no network, no key."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic")

from policylab.llm import LLMError, Task  # noqa: E402
from policylab.llm.anthropic_provider import AnthropicProvider  # noqa: E402
from policylab.schemas import GroundedAnswer  # noqa: E402


class FakeMessages:
    def __init__(self, text, stop_reason="end_turn", model="claude-sonnet-5-5"):
        self.text, self.stop_reason, self.model = text, stop_reason, model
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            stop_reason=self.stop_reason,
            model=self.model,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


def provider(text, **kw):
    msgs = FakeMessages(text, **kw)
    client = SimpleNamespace(beta=SimpleNamespace(messages=msgs))
    return AnthropicProvider(client=client), msgs


GOOD = json.dumps(
    {
        "insufficient_evidence": False,
        "missing_information": "",
        "sentences": [{"text": "A.", "citations": ["D:p0001-0001"]}],
    }
)


@pytest.fixture(autouse=True)
def _no_model_override(monkeypatch):
    monkeypatch.delenv("POLICYLAB_MODEL", raising=False)
    monkeypatch.delenv("POLICYLAB_EFFORT", raising=False)


def test_parses_structured_output_and_sends_schema():
    p, msgs = provider(GOOD)
    r = p.structured(system="s", user="u", output_model=GroundedAnswer, task=Task("qa"))
    assert r.parsed.sentences[0].citations == ["D:p0001-0001"]
    call = msgs.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"
    assert "temperature" not in call


def test_model_is_configurable_by_env(monkeypatch):
    monkeypatch.setenv("POLICYLAB_MODEL", "claude-opus-5-5")
    p, msgs = provider(GOOD)
    p.structured(system="s", user="u", output_model=GroundedAnswer, task=Task("qa"))
    assert p.model == "claude-opus-5-5" and msgs.calls[0]["model"] == "claude-opus-5-5"


def test_records_served_model_on_fallback():
    p, _ = provider(GOOD, model="claude-opus-4-8")
    r = p.structured(system="s", user="u", output_model=GroundedAnswer, task=Task("qa"))
    assert r.model == "claude-sonnet-5-5" and r.served_model == "claude-opus-4-8"


def test_refusal_and_truncation_raise():
    for stop in ("refusal", "max_tokens"):
        p, _ = provider(GOOD, stop_reason=stop)
        with pytest.raises(LLMError):
            p.structured(system="s", user="u", output_model=GroundedAnswer, task=Task("qa"))


def test_invalid_output_raises():
    p, _ = provider('{"sentences": "nope"}')
    with pytest.raises(LLMError):
        p.structured(system="s", user="u", output_model=GroundedAnswer, task=Task("qa"))
