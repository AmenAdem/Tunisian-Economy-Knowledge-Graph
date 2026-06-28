"""
LLM abstraction layer.

Supports multiple LLM providers: OpenRouter, Ollama, OpenAI, etc.
"""

from .base import BaseLLMClient
from .openrouter_client import OpenRouterClient
from .ollama_client import OllamaClient

__all__ = ["BaseLLMClient", "OpenRouterClient", "OllamaClient"]
