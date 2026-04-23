import unittest
from unittest.mock import patch

import aiohttp

from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter, ProviderRequestError


class RouterHardeningV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_route_fallback_records_provider_health(self):
        settings = Settings(openai_api_key="x", openrouter_api_key="y")

        class FakeRouter(ModelRouter):
            async def call_openai(self, prompt: str, task_type: str):
                raise ProviderRequestError("boom")

            async def call_openrouter(self, prompt: str, task_type: str):
                return {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"total_tokens": 1},
                    "model": "fake-openrouter",
                }

        router = FakeRouter(settings)
        result = await router.route("planning", "hello")
        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(router.get_provider_health()["openai"]["failures"], 1)
        self.assertEqual(router.get_provider_health()["openrouter"]["successes"], 1)
        await router.close()

    async def test_cooldown_skips_failed_provider(self):
        settings = Settings(openai_api_key="x", openrouter_api_key="y", provider_health_cooldown_seconds=60)

        class FakeRouter(ModelRouter):
            def __init__(self, settings):
                super().__init__(settings)
                self.calls = []

            async def call_openai(self, prompt: str, task_type: str):
                self.calls.append("openai")
                raise ProviderRequestError("boom")

            async def call_openrouter(self, prompt: str, task_type: str):
                self.calls.append("openrouter")
                return {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {},
                    "model": "fake-openrouter",
                }

        router = FakeRouter(settings)
        router._record_provider_failure("openai", "boom")
        result = await router.route("planning", "hello")
        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(router.calls, ["openrouter"])
        await router.close()

    async def test_session_is_reused(self):
        settings = Settings()
        created = []

        class DummySession:
            def __init__(self, *args, **kwargs):
                self.closed = False
                created.append(self)

            async def close(self):
                self.closed = True

        router = ModelRouter(settings)
        with patch.object(aiohttp, "ClientSession", DummySession):
            first = await router._get_session()
            second = await router._get_session()
            self.assertIs(first, second)
            self.assertEqual(len(created), 1)
            await router.close()


if __name__ == "__main__":
    unittest.main()
