import unittest
from unittest.mock import AsyncMock
from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter, ProviderNotConfiguredError, ProviderRequestError


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = Settings()

    def test_choose_provider_no_keys(self):
        router = ModelRouter(self.settings)
        with self.assertRaises(ProviderNotConfiguredError):
            router.choose_provider("analysis")

    def test_choose_provider_planning_uses_ollama_fallback(self):
        router = ModelRouter(self.settings)
        self.assertEqual(router.choose_provider("planning"), "ollama")

    def test_normalize_openai_response(self):
        router = ModelRouter(self.settings)
        data = {"choices": [{"message": {"content": "test"}}], "usage": {"tokens": 10}}
        normalized = router._normalize_response("openai", data)
        self.assertEqual(normalized["text"], "test")
        self.assertIn("usage", normalized)

    async def test_router_fallback_to_next_provider(self):
        settings = Settings(openai_api_key="x", openrouter_api_key="y")
        router = ModelRouter(settings)
        router.call_openai = AsyncMock(side_effect=ProviderRequestError("boom"))
        router.call_openrouter = AsyncMock(return_value={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
            "model": "gpt-4o-mini",
        })
        result = await router.route("planning", "test")
        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(result["text"], "ok")


if __name__ == "__main__":
    unittest.main()
