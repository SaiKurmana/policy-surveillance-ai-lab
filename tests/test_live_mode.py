"""Live LLM mode needs an API key, a LIVE_MODE_PASSWORD secret, and the matching password."""

import pytest

from policylab.llm import live_mode_unlocked


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.delenv("POLICYLAB_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("LIVE_MODE_PASSWORD", "open-sesame")


def test_unlocks_only_with_matching_password(configured):
    assert live_mode_unlocked("open-sesame")
    assert not live_mode_unlocked("wrong")
    assert not live_mode_unlocked("")
    assert not live_mode_unlocked(None)


def test_key_without_password_secret_stays_demo(configured, monkeypatch):
    monkeypatch.delenv("LIVE_MODE_PASSWORD")
    assert not live_mode_unlocked("open-sesame")
    assert not live_mode_unlocked("")


def test_password_without_key_stays_demo(configured, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert not live_mode_unlocked("open-sesame")


def test_mock_provider_env_forces_demo(configured, monkeypatch):
    monkeypatch.setenv("POLICYLAB_PROVIDER", "mock")
    assert not live_mode_unlocked("open-sesame")
