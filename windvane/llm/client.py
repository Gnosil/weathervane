"""Anthropic Messages API wrapper."""

from __future__ import annotations

from anthropic import Anthropic

LLMClient = Anthropic  # re-export under our own name


def make_client(api_key: str) -> Anthropic:
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env.")
    return Anthropic(api_key=api_key)
