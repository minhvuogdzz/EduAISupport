"""REFORM-1 (Task 1.1, 1.3): the tutor speaks with Qwen whenever a Groq key is set, unless told not to."""

import pytest
from cavat.config import Settings


def settings(monkeypatch, **env):
    for name in ("GROQ_API_KEY", "TUTOR_RENDERER", "MAX_LLM_CALLS_PER_SESSION"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


@pytest.mark.parametrize(
    ("env", "renderer"),
    [
        ({"GROQ_API_KEY": "gsk_test"}, "llm"),
        ({}, "template"),
        ({"GROQ_API_KEY": ""}, "template"),  # the tests blank the key (conftest.py)
        ({"GROQ_API_KEY": "  "}, "template"),
        ({"GROQ_API_KEY": "gsk_test", "TUTOR_RENDERER": "template"}, "template"),  # said outright: kept
        ({"TUTOR_RENDERER": "llm"}, "llm"),  # no key: the router answers use_template on every call
    ],
)
def test_the_renderer_follows_the_groq_key(monkeypatch, env, renderer):
    assert settings(monkeypatch, **env).tutor_renderer == renderer


def test_a_session_may_call_the_model_forty_times(monkeypatch):
    """DI-68: 40 calls of 1.126 token on average are 45.000 of the 200.000 token a day of a Groq project."""
    assert settings(monkeypatch).max_llm_calls_per_session == 40
    assert settings(monkeypatch, MAX_LLM_CALLS_PER_SESSION="15").max_llm_calls_per_session == 15
