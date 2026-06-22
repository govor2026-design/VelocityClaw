from velocity_claw.api.dashboard_filters import compact_step_inspector, filter_runs, run_profile
from velocity_claw.api.dashboard_runs_v2 import render_dashboard_runs_v2
from velocity_claw.api.dashboard_v2 import render_dashboard_v2


def sample_runs():
    return [
        {
            "run_id": "run-safe",
            "task": "Safe completed run",
            "status": "completed",
            "created_at": "2026-06-22T08:00:00",
            "context": {"execution_profile": "safe"},
            "steps": [
                {"id": 1, "title": "Inspect", "tool": "git.inspect", "status": "completed", "result": {"branch": "master"}},
                {"id": 2, "title": "Test", "tool": "test.run", "status": "failed", "error": "assertion failed", "result": "x" * 300},
            ],
            "artifacts": [{"name": "test_output"}],
        },
        {
            "run_id": "run-owner",
            "task": "Owner failed run",
            "status": "failed",
            "created_at": "2026-06-22T08:05:00",
            "execution_profile": "owner",
            "steps": [],
            "artifacts": [],
        },
    ]


def test_filter_runs_by_status_and_profile():
    runs = sample_runs()

    assert [run["run_id"] for run in filter_runs(runs, status="completed")] == ["run-safe"]
    assert [run["run_id"] for run in filter_runs(runs, profile="owner")] == ["run-owner"]
    assert [run["run_id"] for run in filter_runs(runs, status="failed", profile="owner")] == ["run-owner"]
    assert filter_runs(runs, status="running") == []


def test_run_profile_supports_direct_and_context_values():
    runs = sample_runs()

    assert run_profile(runs[0]) == "safe"
    assert run_profile(runs[1]) == "owner"
    assert run_profile({}) is None


def test_compact_step_inspector_limits_result_preview():
    inspector = compact_step_inspector(sample_runs()[0])

    assert inspector["run_id"] == "run-safe"
    assert inspector["profile"] == "safe"
    assert inspector["step_count"] == 2
    assert inspector["artifact_count"] == 1
    assert inspector["steps"][1]["error"] == "assertion failed"
    assert len(inspector["steps"][1]["result_preview"]) == 240
    assert inspector["steps"][1]["result_preview"].endswith("...")


def test_runs_inspector_renders_filters_and_selected_steps():
    runs = sample_runs()
    html = render_dashboard_runs_v2(
        runs=runs,
        status="completed",
        profile="safe",
        selected_run=runs[0],
    )

    assert "Runs and steps inspector" in html
    assert "Filtered runs: 1 of 2" in html
    assert "run-safe" in html
    assert "run-owner" not in html
    assert "git.inspect" in html
    assert "assertion failed" in html
    assert "/runs/run-safe/artifacts/v2" in html
    assert "option value='completed' selected" in html
    assert "option value='safe' selected" in html


def test_main_dashboard_links_to_runs_inspector():
    html = render_dashboard_v2(
        execution_profile="safe",
        safe_mode=True,
        trusted_mode=False,
        release_state={"readiness": "ready", "score": 1, "total_checks": 1},
        console={"queue": {}, "approvals": {}},
        recent_runs=sample_runs()[:1],
        approvals=[],
        queue_jobs=[],
        metrics={},
        provider_observability={"summary": {}},
        provider_health={},
        last_failed=None,
    )

    assert "/dashboard/v2/runs" in html
    assert "/dashboard/v2/runs?run_id=run-safe" in html
