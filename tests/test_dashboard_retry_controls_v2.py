import unittest

from velocity_claw.api.dashboard_retry_controls import build_retry_controls


class DashboardRetryControlsV2Tests(unittest.TestCase):
    def test_failed_run_has_retry_controls(self):
        controls = build_retry_controls({
            "run_id": "run-1",
            "task": "fix tests",
            "status": "failed",
        })
        self.assertTrue(controls["available"])
        self.assertEqual(controls["reason"], "retryable")
        self.assertEqual(controls["links"]["retry_context"], "/runs/run-1/retry-context")
        self.assertEqual(controls["links"]["retry_post"], "/runs/run-1/retry")
        self.assertIn("Retry controls", controls["html"])
        self.assertIn("POST /runs/run-1/retry", controls["html"])

    def test_completed_run_is_not_retryable(self):
        controls = build_retry_controls({
            "run_id": "run-2",
            "task": "done",
            "status": "completed",
        })
        self.assertFalse(controls["available"])
        self.assertEqual(controls["reason"], "status_not_retryable")
        self.assertIn("not retryable", controls["html"])

    def test_missing_run_has_no_controls(self):
        controls = build_retry_controls(None)
        self.assertFalse(controls["available"])
        self.assertEqual(controls["reason"], "no_run")


if __name__ == "__main__":
    unittest.main()
