"""
Ollama LLM client (backward compatibility).
"""

import json
from typing import Dict, Optional

import ollama
from loguru import logger

from .base import BaseLLMClient


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
    ):
        """
        Initialize Ollama client.

        Args:
            host: Ollama server URL
            model: Model name
        """
        self.client = ollama.Client(host=host)
        self.model = model
        logger.info(f"Ollama client initialized: {model} at {host}")

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """Generate completion from Ollama."""
        import time
        start_time = time.time()

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        logger.trace(f"📤 Ollama Request:")
        logger.trace(f"  Model: {self.model}")
        logger.trace(f"  Temperature: {temperature}")
        logger.trace(f"  Max Tokens: {max_tokens}")
        logger.trace(f"  System Prompt Length: {len(system_prompt) if system_prompt else 0} chars")
        logger.trace(f"  User Prompt Length: {len(prompt)} chars")
        logger.trace(f"  Full User Prompt:\n{prompt[:500]}{'...' if len(prompt) > 500 else ''}")

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            elapsed_time = time.time() - start_time
            content = response["message"]["content"]

            logger.debug(f"Ollama completion: {len(content)} chars in {elapsed_time:.2f}s")
            logger.trace(f"📥 Ollama Response (took {elapsed_time:.2f}s):")
            logger.trace(f"  Response Length: {len(content)} chars")
            logger.trace(f"  Full Response:\n{content[:1000]}{'...' if len(content) > 1000 else ''}")

            return content

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Ollama error after {elapsed_time:.2f}s: {e}")
            logger.trace(f"  Error type: {type(e).__name__}")
            raise

    def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict:
        """Generate JSON completion."""
        json_instruction = "\n\nRespond with valid JSON only."
        if system_prompt:
            system_prompt = system_prompt + json_instruction
        else:
            system_prompt = "Respond in JSON format." + json_instruction

        response_text = self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Parse JSON
        try:
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            return json.loads(response_text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Invalid JSON from Ollama: {e}")

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            self.client.list()
            return True
        except Exception:
            return False
