import asyncio
import json
from typing import Optional
import requests
from velocity_claw.config.settings import Settings
from velocity_claw.logs.logger import get_logger


class ModelRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("velocity_claw.models")

    async def route(self, task_type: str, prompt: str) -> str:
        provider = self.choose_provider(task_type)
        self.logger.info("Routing %s task to provider %s", task_type, provider)
        if provider == "openai":
            return self.call_openai(prompt, task_type)
        if provider == "anthropic":
            return self.call_anthropic(prompt, task_type)
        if provider == "gemini":
            return self.call_gemini(prompt, task_type)
        if provider == "openrouter":
            return self.call_openrouter(prompt, task_type)
        if provider == "ollama":
            return self.call_ollama(prompt, task_type)
        return self.call_openai(prompt, task_type)

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
        return "openai"

    def call_openai(self, prompt: str, task_type: str) -> str:
        if not self.settings.openai_api_key:
            return "OpenAI API key not configured."
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}
        model = "gpt-4o-mini" if task_type == "code" else "gpt-4o-mini"
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": "Velocity Claw assistant."}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 800,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def call_openrouter(self, prompt: str, task_type: str) -> str:
        if not self.settings.openrouter_api_key:
            return "OpenRouter API key not configured."
        url = "https://api.openrouter.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.openrouter_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": "Velocity Claw assistant."}, {"role": "user", "content": prompt}],
            "temperature": 0.25,
            "max_tokens": 700,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def call_anthropic(self, prompt: str, task_type: str) -> str:
        if not self.settings.anthropic_api_key:
            return "Anthropic API key not configured."
        url = "https://api.anthropic.com/v1/complete"
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "Content-Type": "application/json",
        }
        model = "claude-3.5-sonic" if task_type in ["fast", "summarize"] else "claude-3.5"
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens_to_sample": 700,
            "temperature": 0.2,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        data = response.json()
        return data.get("completion", "")

    def call_gemini(self, prompt: str, task_type: str) -> str:
        if not self.settings.gemini_api_key:
            return "Gemini API key not configured."
        url = "https://gemini.googleapis.com/v1beta2/models/text-bison-001:generate"
        headers = {"Authorization": f"Bearer {self.settings.gemini_api_key}", "Content-Type": "application/json"}
        payload = {"prompt": {"text": prompt}, "temperature": 0.2, "maxOutputTokens": 700}
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        data = response.json()
        return data.get("candidates", [{}])[0].get("output", "")

    def call_ollama(self, prompt: str, task_type: str) -> str:
        url = f"{self.settings.ollama_url}/api/v1/complete"
        payload = {"model": "llama2", "prompt": prompt, "max_tokens": 700, "temperature": 0.25}
        response = requests.post(url, json=payload, timeout=60)
        data = response.json()
        return data.get("completion", "")
