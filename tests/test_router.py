import unittest
import asyncio
from velocity_claw.config.settings import Settings
from velocity_claw.models.router import ModelRouter, ProviderNotConfiguredError


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()

    def test_choose_provider_no_keys(self):
        router = ModelRouter(self.settings)
        with self.assertRaises(ProviderNotConfiguredError):
            router.choose_provider("analysis")

    def test_normalize_openai_response(self):
        router = ModelRouter(self.settings)
        data = {"choices": [{"message": {"content": "test"}}], "usage": {"tokens": 10}}
        normalized = router._normalize_response("openai", data)
        self.assertEqual(normalized["text"], "test")
        self.assertIn("usage", normalized)


if __name__ == "__main__":
    unittest.main()