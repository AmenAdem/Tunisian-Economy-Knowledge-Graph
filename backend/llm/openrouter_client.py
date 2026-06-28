"""
OpenRouter LLM client.

Supports multiple models through OpenRouter API including free models.
"""

import json
import time
from typing import Dict, Optional

import requests
from loguru import logger

from .base import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    """
    OpenRouter API client.

    Supports models like:
    - nvidia/llama-3.1-nemotron-70b-instruct (free)
    - meta-llama/llama-3.2-3b-instruct (free)
    - google/gemini-2.0-flash-exp (free)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/llama-3.1-nemotron-70b-instruct:free",
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: str = "Tunisian Economy Graph",
        timeout: int = 120,  # Increased from 60s
        max_retries: int = 3,
    ):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model: Model identifier (append :free for free models)
            base_url: OpenRouter API base URL
            app_name: Application name for tracking
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limit tracking
        self.rate_limit_remaining = None
        self.rate_limit_reset_time = None

        logger.info(f"OpenRouter client initialized with model: {model}, timeout: {timeout}s")

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        Generate completion from OpenRouter with retry logic.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional OpenRouter parameters

        Returns:
            Generated text
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/yourusername/tun-economy-graph",
            "X-Title": self.app_name,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                import time
                start_time = time.time()

                logger.debug(f"OpenRouter request attempt {attempt + 1}/{self.max_retries}")
                logger.trace(f"📤 OpenRouter Request:")
                logger.trace(f"  Model: {self.model}")
                logger.trace(f"  Temperature: {temperature}")
                logger.trace(f"  Max Tokens: {max_tokens}")
                logger.trace(f"  System Prompt Length: {len(system_prompt) if system_prompt else 0} chars")
                logger.trace(f"  User Prompt Length: {len(prompt)} chars")
                logger.trace(f"  Full User Prompt:\n{prompt[:500]}{'...' if len(prompt) > 500 else ''}")

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                # Track rate limits from response headers
                self._update_rate_limits(response.headers)

                response.raise_for_status()

                elapsed_time = time.time() - start_time
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                logger.debug(f"OpenRouter completion: {len(content)} chars in {elapsed_time:.2f}s")
                logger.trace(f"📥 OpenRouter Response (took {elapsed_time:.2f}s):")
                logger.trace(f"  Response Length: {len(content)} chars")
                logger.trace(f"  Full Response:\n{content[:1000]}{'...' if len(content) > 1000 else ''}")

                # Log token usage if available
                if "usage" in data:
                    usage = data["usage"]
                    logger.trace(f"  Token Usage:")
                    logger.trace(f"    Prompt: {usage.get('prompt_tokens', 'N/A')}")
                    logger.trace(f"    Completion: {usage.get('completion_tokens', 'N/A')}")
                    logger.trace(f"    Total: {usage.get('total_tokens', 'N/A')}")

                return content

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError) as e:
                last_error = e
                elapsed_time = time.time() - start_time
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s

                logger.trace(f"⚠️  OpenRouter request failed after {elapsed_time:.2f}s: {type(e).__name__}")

                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"OpenRouter connection error (attempt {attempt + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"OpenRouter API failed after {self.max_retries} attempts: {e}")
                    logger.trace(f"  Total time spent: {elapsed_time:.2f}s")
                    raise

            except requests.exceptions.RequestException as e:
                # Handle rate limit errors specifically
                if hasattr(e, "response") and e.response is not None:
                    # Track rate limits even on error
                    self._update_rate_limits(e.response.headers)

                    if e.response.status_code == 429:
                        self._handle_rate_limit_error(e.response)

                    logger.error(f"OpenRouter API error: {e}")
                    logger.error(f"Response: {e.response.text}")
                else:
                    logger.error(f"OpenRouter API error: {e}")
                raise

        # Should not reach here, but just in case
        raise last_error if last_error else Exception("OpenRouter request failed")

    def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict:
        """
        Generate JSON completion.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dict
        """
        # Add JSON instruction to system prompt
        json_instruction = "\n\nYou MUST respond with valid JSON only. No markdown, no explanation, just pure JSON."
        if system_prompt:
            system_prompt = system_prompt + json_instruction
        else:
            system_prompt = "You are a helpful assistant that responds in JSON format." + json_instruction

        # Request JSON response format
        kwargs["response_format"] = {"type": "json_object"}

        response_text = self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Parse JSON
        try:
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            return json.loads(response_text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def is_available(self) -> bool:
        """Check if OpenRouter API is available."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Try a minimal request
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"OpenRouter availability check failed: {e}")
            return False

    def list_models(self) -> list:
        """
        List available models on OpenRouter.

        Returns:
            List of model identifiers
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            models = [model["id"] for model in data.get("data", [])]

            logger.info(f"Found {len(models)} available models")
            return models

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def _update_rate_limits(self, headers: dict) -> None:
        """Update rate limit tracking from response headers."""
        try:
            if "x-ratelimit-remaining" in headers:
                self.rate_limit_remaining = int(headers["x-ratelimit-remaining"])

            if "x-ratelimit-reset" in headers:
                # Reset time is in milliseconds
                reset_ms = int(headers["x-ratelimit-reset"])
                self.rate_limit_reset_time = reset_ms / 1000

            # Log rate limit status
            if self.rate_limit_remaining is not None:
                logger.info(f"⚡ Rate limit: {self.rate_limit_remaining} requests remaining")

                # Warn if getting low
                if self.rate_limit_remaining < 10:
                    from datetime import datetime
                    if self.rate_limit_reset_time:
                        reset_time = datetime.fromtimestamp(self.rate_limit_reset_time)
                        logger.warning(
                            f"⚠️  LOW RATE LIMIT: Only {self.rate_limit_remaining} requests left! "
                            f"Resets at {reset_time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    else:
                        logger.warning(f"⚠️  LOW RATE LIMIT: Only {self.rate_limit_remaining} requests left!")

        except (ValueError, KeyError) as e:
            logger.trace(f"Could not parse rate limit headers: {e}")

    def _handle_rate_limit_error(self, response) -> None:
        """Handle 429 rate limit errors with helpful messages."""
        from datetime import datetime

        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Rate limit exceeded")

            logger.error(f"🚫 RATE LIMIT EXCEEDED: {error_msg}")

            # Extract reset time from headers
            if "x-ratelimit-reset" in response.headers:
                reset_ms = int(response.headers["x-ratelimit-reset"])
                reset_time = datetime.fromtimestamp(reset_ms / 1000)
                logger.error(f"   Rate limit resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Calculate wait time
                import time
                wait_seconds = (reset_ms / 1000) - time.time()
                if wait_seconds > 0:
                    hours = int(wait_seconds // 3600)
                    minutes = int((wait_seconds % 3600) // 60)
                    logger.error(f"   Time until reset: {hours}h {minutes}m")

            # Show helpful advice
            logger.error("   💡 Solutions:")
            logger.error("      1. Add credits to OpenRouter ($10 = 1000 free requests/day)")
            logger.error("      2. Wait for rate limit to reset")
            logger.error("      3. Switch to Ollama (set LLM_PROVIDER=ollama in .env)")

        except Exception as e:
            logger.trace(f"Could not parse rate limit error: {e}")

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status."""
        return {
            "remaining": self.rate_limit_remaining,
            "reset_time": self.rate_limit_reset_time,
        }
