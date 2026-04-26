import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from velocity_claw.api.retry_routes import register_retry_routes


def ok(payload_key, payload, **extra):
    body = {"status": "ok", payload_key: payload}
    body.update(extra)
    return body


class RetryReplayApiRoutesV2Tests(unittest.TestCase):
    def make_client(self, agent):
        app = FastAPI()
        app.state.agent = agent
        register_retry_routes(app, ok)
        return TestClient(app)

    def test_retry_context_route_returns_structured_context(self):
        agent = SimpleNamespace(
            build_retry_context=lambda run_id: {
                "retry": {
                    "source_run_id": run_id,
                    "recommended_strategy": {"mode": "inspect_failed_step_first"},
                }
            },
            retry_run=AsyncMock(),
        )
        client = self.make_client(agent)
        response = client.get("/runs/run-1/retry-context")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["retry_context"]["retry"]["source_run_id"], "run-1")
        self.assertEqual(payload["retry_context"]["retry"]["recommended_strategy"]["mode"], "inspect_failed_step_first")

    def test_retry_context_route_returns_404_for_missing_run(self):
        def missing(_run_id):
            raise ValueError("run_not_found")

        agent = SimpleNamespace(build_retry_context=missing, retry_run=AsyncMock())
        client = self.make_client(agent)
        response = client.get("/runs/missing/retry-context")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["error"], "not_found")

    def test_retry_route_returns_retry_result(self):
        agent = SimpleNamespace(
            build_retry_context=lambda run_id: {"retry": {"source_run_id": run_id}},
            retry_run=AsyncMock(return_value={"run_id": "retry-1", "status": "completed"}),
        )
        client = self.make_client(agent)
        response = client.post("/runs/run-1/retry")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(payload["retry"]["run_id"], "retry-1")
        self.assertEqual(payload["retry"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
