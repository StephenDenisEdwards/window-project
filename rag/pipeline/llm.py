"""Unified LLM chat interface for Anthropic and Ollama.

Replaces the per-notebook client setup and `llm_chat` definition.
Clients are created lazily on first use so importing this module never
touches the network or requires an API key.
"""
from __future__ import annotations

import functools

import anthropic
from openai import OpenAI


@functools.cache
def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


@functools.cache
def _ollama_client(base_url: str) -> OpenAI:
    return OpenAI(base_url=f"{base_url}/v1", api_key="ollama")


def llm_chat(
    prompt: str,
    *,
    provider: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    ollama_base_url: str = "http://localhost:11434",
) -> str:
    """Send a single-message prompt and return the response text.

    `provider` must be ``"anthropic"`` or ``"ollama"``.
    """
    if provider == "anthropic":
        response = _anthropic_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    if provider == "ollama":
        response = _ollama_client(ollama_base_url).chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    raise ValueError(f"Unknown provider: {provider!r}. Use 'anthropic' or 'ollama'.")
