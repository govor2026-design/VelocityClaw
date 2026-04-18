import asyncio
import json
from typing import Dict, Optional
import aiohttp
from velocity_claw.config.settings import Settings
from velocity_claw.logs.logger import get_logger


class ProviderNotConfiguredError(Exception):
    pass


class ProviderRequestError(Exception):
    pass


class ProviderResponseError(Exception):
    pass


class ModelRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("velocity_claw.models")
        self.timeout = aiohttp.ClientTimeout(total=60)

    async def route(self, task_type: str, prompt: str) -> Dict:
        provider = self.choose_provider(task_type)
        self.logger.info("Routing %s task to provider %s", task_type, provider)

        for attempt in range(3):  # Retry up to 3 times
            try:
                if provider == "openai":
                    response = await self.call_openai(prompt, task_type)
                elif provider == "anthropic":
                    response = await self.call_anthropic(prompt, task_type)
                elif provider == "gemini":
                    response = await self.call_gemini(prompt, task_type)
                elif provider == "openrouter":
                    response = await self.call_openrouter(prompt, task_type)
                elif provider == "ollama":
                    response = await self.call_ollama(prompt, task_type)
                else:
                    response = await self.call_openai(prompt, task_type)

                return self._normalize_response(provider, response)
            except (ProviderNotConfiguredError, ProviderRequestError, ProviderResponseError) as e:
                if attempt == 2:  # Last attempt
                    raise e
                self.logger.warning("Provider %s failed (attempt %d): %s", provider, attempt + 1, e)
                await asyncio.sleep(1)  # Wait before retry

    def choose_provider(self, task_type: str) -> str:
        if task_type in ["code", "planning"]:
            return self._preferred_provider(["openai", "openrouter", "ollama"])
        if task_type in ["analysis", "reasoning"]:
            return self._preferred_provider(["openai", "anthropic", "gemini"])
        if task_type in ["fast", "summarize"]:
            return self._preferred_provider(["openrouter", "ollama", "openai"])
        return self._preferred_provider(self.settings.provider_order)

    def _preferred_provider(self, order):
        for provider in order:
            if getattr(self.settings, f"{provider}_api_key", None) or provider == "ollama":
                return provider
        raise ProviderNotConfiguredError("No providers configured")

    async def call_openai(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.openai_api_key:
            raise ProviderNotConfiguredError("OpenAI API key not configured")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}
        model = "gpt-4o-mini"
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": "Velocity Claw assistant."}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 800,
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def call_openrouter(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.openrouter_api_key:
            raise ProviderNotConfiguredError("OpenRouter API key not configured")

        url = "https://api.openrouter.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.openrouter_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": "Velocity Claw assistant."}, {"role": "user", "content": prompt}],
            "temperature": 0.25,
            "max_tokens": 700,
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def call_anthropic(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.anthropic_api_key:
            raise ProviderNotConfiguredError("Anthropic API key not configured")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        model = "claude-3-5-sonnet-20240620"
        payload = {
            "model": model,
            "max_tokens": 700,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}]
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def call_gemini(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.gemini_api_key:
            raise ProviderNotConfiguredError("Gemini API key not configured")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.settings.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700}
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def call_ollama(self, prompt: str, task_type: str) -> Dict:
        url = f"{self.settings.ollama_url}/api/generate"
        payload = {"model": "llama2", "prompt": prompt, "stream": False}

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    def _normalize_response(self, provider: str, data: Dict) -> Dict:
        try:
            if provider == "openai" or provider == "openrouter":
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
            elif provider == "anthropic":
                text = data.get("content", [{}])[0].get("text", "")
                usage = data.get("usage", {})
            elif provider == "gemini":
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                usage = {}
            elif provider == "ollama":
                text = data.get("response", "")
                usage = {}
            else:
                raise ProviderResponseError(f"Unknown provider: {provider}")

            if not text:
                raise ProviderResponseError("Empty response from provider")

            return {
                "provider": provider,
                "model": data.get("model", "unknown"),
                "text": text,
                "usage": usage,
                "raw": data
            }
        except KeyError as e:
            raise ProviderResponseError(f"Invalid response format: {e}")
