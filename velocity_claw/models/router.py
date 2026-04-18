from typing import Dict, List
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
        providers = self._provider_candidates(task_type)
        errors: List[str] = []
        for provider in providers:
            self.logger.info("Routing %s task to provider %s", task_type, provider)
            try:
                response = await self._call_provider(provider, prompt, task_type)
                return self._normalize_response(provider, response)
            except (ProviderNotConfiguredError, ProviderRequestError, ProviderResponseError) as e:
                self.logger.warning("Provider %s failed: %s", provider, e)
                errors.append(f"{provider}: {e}")
                continue
        raise ProviderRequestError("All providers failed: " + "; ".join(errors) if errors else "No providers available")

    def choose_provider(self, task_type: str) -> str:
        providers = self._provider_candidates(task_type)
        if not providers:
            raise ProviderNotConfiguredError("No providers configured")
        return providers[0]

    def _provider_candidates(self, task_type: str) -> List[str]:
        if task_type in ["code", "planning"]:
            preferred = ["openai", "openrouter", "ollama"]
        elif task_type in ["analysis", "reasoning"]:
            preferred = ["openai", "anthropic", "gemini"]
        elif task_type in ["fast", "summarize"]:
            preferred = ["openrouter", "ollama", "openai"]
        else:
            preferred = self.settings.provider_order
        return [provider for provider in preferred if self._is_provider_available(provider)]

    def _is_provider_available(self, provider: str) -> bool:
        if provider == "ollama":
            return True
        return bool(getattr(self.settings, f"{provider}_api_key", None))

    async def _call_provider(self, provider: str, prompt: str, task_type: str) -> Dict:
        if provider == "openai":
            return await self.call_openai(prompt, task_type)
        if provider == "anthropic":
            return await self.call_anthropic(prompt, task_type)
        if provider == "gemini":
            return await self.call_gemini(prompt, task_type)
        if provider == "openrouter":
            return await self.call_openrouter(prompt, task_type)
        if provider == "ollama":
            return await self.call_ollama(prompt, task_type)
        raise ProviderNotConfiguredError(f"Unknown provider: {provider}")

    async def _post_json(self, url: str, *, headers=None, payload=None) -> Dict:
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientResponseError as e:
            raise ProviderRequestError(f"HTTP {e.status}: {e.message}")
        except aiohttp.ClientError as e:
            raise ProviderRequestError(str(e))

    async def call_openai(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.openai_api_key:
            raise ProviderNotConfiguredError("OpenAI API key not configured")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": "Velocity Claw assistant."}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 800,
        }
        data = await self._post_json(url, headers=headers, payload=payload)
        data.setdefault("model", payload["model"])
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
        data = await self._post_json(url, headers=headers, payload=payload)
        data.setdefault("model", payload["model"])
        return data

    async def call_anthropic(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.anthropic_api_key:
            raise ProviderNotConfiguredError("Anthropic API key not configured")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 700,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = await self._post_json(url, headers=headers, payload=payload)
        data.setdefault("model", payload["model"])
        return data

    async def call_gemini(self, prompt: str, task_type: str) -> Dict:
        if not self.settings.gemini_api_key:
            raise ProviderNotConfiguredError("Gemini API key not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.settings.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
        }
        data = await self._post_json(url, payload=payload)
        data.setdefault("model", "gemini-pro")
        return data

    async def call_ollama(self, prompt: str, task_type: str) -> Dict:
        url = f"{self.settings.ollama_url}/api/generate"
        payload = {"model": "llama2", "prompt": prompt, "stream": False}
        data = await self._post_json(url, payload=payload)
        data.setdefault("model", payload["model"])
        return data

    def _normalize_response(self, provider: str, data: Dict) -> Dict:
        try:
            if provider in {"openai", "openrouter"}:
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
                "raw": data,
            }
        except (IndexError, KeyError, TypeError) as e:
            raise ProviderResponseError(f"Invalid response format: {e}")
