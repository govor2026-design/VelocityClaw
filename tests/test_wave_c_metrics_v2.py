import tempfile
import unittest
from pathlib import Path

from velocity_claw.api.server import create_app
from velocity_claw.core.metrics import MetricsRegistry


class MetricsDiagnosticsV2Tests(unittest.TestCase):
    def test_metrics_registry_has_diagnostics_summary(self):
        registry = MetricsRegistry()
        registry.incr("tasks_total")
        registry.incr("tasks_completed")
        registry.observe_task_duration(120)
        registry.observe_task_duration(80)
        summary = registry.diagnostics_summary()
        self.assertIn("task_health", summary)
        self.assertEqual(summary["task_health"]["avg_duration_ms"], 100)

    def test_app_exposes_diagnostics_shape(self):
        tmp = tempfile.mkdtemp()
        Path(tmp, ".keep").write_text("x")
        app = create_app()
        self.assertTrue(hasattr(app.state, "metrics"))
        data = app.state.metrics.snapshot()
        self.assertIn("avg_task_duration_ms", data)


if __name__ == "__main__":
    unittest.main()
