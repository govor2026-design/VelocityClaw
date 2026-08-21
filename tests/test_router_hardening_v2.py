import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter, ProviderRequestError


class FakeHttpResponse:
    def __init__(self, status, payload=None, message=""):
        self.status = status
        self.payload = payload or {}
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                None,
                (),
                status=self.status,
                message=self.message,
            )

    async def json(self):
        return self.payload


class FakeHttpSession:
    closed = False

    def __init__(self, *responses):
        self.calls = 0
        self.responses = list(responses)

    def post(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


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

    async def test_malformed_response_is_only_recorded_as_failure(self):
        settings = Settings(openai_api_key="x", openrouter_api_key="y")

        class FakeRouter(ModelRouter):
            async def call_openai(self, prompt: str, task_type: str):
                return {}

            async def call_openrouter(self, prompt: str, task_type: str):
                return {
                    "choices": [{"message": {"content": "fallback ok"}}],
                    "usage": {},
                    "model": "fake-openrouter",
                }

        router = FakeRouter(settings)
        result = await router.route("planning", "hello")

        self.assertEqual(result["provider"], "openrouter")
        openai_health = router.get_provider_health()["openai"]
        self.assertEqual(openai_health["requests"], 1)
        self.assertEqual(openai_health["successes"], 0)
        self.assertEqual(openai_health["failures"], 1)
        self.assertEqual(len(router.route_history), 1)
        self.assertEqual(
            router.route_history[0]["attempts"],
            [
                {"provider": "openai", "status": "failed", "error": "Empty response from provider"},
                {"provider": "openrouter", "status": "success"},
            ],
        )
        await router.close()

    async def test_timeout_retries_then_falls_back_to_next_provider(self):
        settings = Settings(
            openai_api_key="x",
            openrouter_api_key="y",
            provider_max_retries=2,
            provider_retry_backoff_ms=0,
            provider_request_timeout_seconds=7,
        )

        class TimeoutRequest:
            async def __aenter__(self):
                raise asyncio.TimeoutError("provider stalled")

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        class TimeoutSession:
            closed = False

            def __init__(self):
                self.calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                return TimeoutRequest()

        class FakeRouter(ModelRouter):
            def __init__(self, settings):
                super().__init__(settings)
                self.timeout_session = TimeoutSession()

            async def _get_session(self):
                return self.timeout_session

            async def call_openrouter(self, prompt: str, task_type: str):
                return {
                    "choices": [{"message": {"content": "fallback ok"}}],
                    "usage": {},
                    "model": "fake-openrouter",
                }

        router = FakeRouter(settings)
        result = await router.route("planning", "hello")

        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(router.timeout_session.calls, 3)
        openai_health = router.get_provider_health()["openai"]
        self.assertEqual(openai_health["requests"], 1)
        self.assertEqual(openai_health["failures"], 1)
        self.assertEqual(
            router.route_history[0]["attempts"],
            [
                {
                    "provider": "openai",
                    "status": "failed",
                    "error": "Provider request timed out after 7s",
                },
                {"provider": "openrouter", "status": "success"},
            ],
        )
        await router.close()

    async def test_rate_limit_response_is_retried(self):
        settings = Settings(provider_max_retries=2, provider_retry_backoff_ms=0)
        router = ModelRouter(settings)
        session = FakeHttpSession(
            FakeHttpResponse(429, message="Too Many Requests"),
            FakeHttpResponse(200, {"result": "ok"}),
        )
        router._get_session = AsyncMock(return_value=session)

        result = await router._post_json("https://provider.invalid", payload={})

        self.assertEqual(result, {"result": "ok"})
        self.assertEqual(session.calls, 2)

    async def test_non_retryable_client_error_fails_immediately(self):
        settings = Settings(provider_max_retries=2, provider_retry_backoff_ms=0)
        router = ModelRouter(settings)
        session = FakeHttpSession(FakeHttpResponse(401, message="Unauthorized"))
        router._get_session = AsyncMock(return_value=session)

        with self.assertRaisesRegex(ProviderRequestError, "HTTP 401: Unauthorized"):
            await router._post_json("https://provider.invalid", payload={})

        self.assertEqual(session.calls, 1)

    async def test_gemini_api_key_is_sent_in_header_not_url(self):
        secret = "gemini-secret-value"
        router = ModelRouter(Settings(gemini_api_key=secret))
        router._post_json = AsyncMock(
            return_value={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )

        response = await router.call_gemini("hello", "analysis")

        self.assertEqual(response["model"], "gemini-pro")
        url = router._post_json.await_args.args[0]
        kwargs = router._post_json.await_args.kwargs
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        )
        self.assertNotIn(secret, url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], secret)
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        await router.close()


if __name__ == "__main__":
    unittest.main()
