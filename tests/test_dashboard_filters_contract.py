from velocity_claw.api.app import create_app
from velocity_claw.api.dashboard_filters import compact_step_inspector, filter_runs, run_profile


def test_app_module_imports_with_dashboard_filters_available() -> None:
    assert callable(create_app)


def test_run_profile_reads_execution_profile_contract() -> None:
    assert run_profile({"execution_profile": "DEV"}) == "dev"
    assert run_profile({"context": {"execution_profile": "owner"}}) == "owner"


def test_filter_runs_supports_queued_and_awaiting_approval() -> None:
    runs = [
        {"run_id": "1", "status": "queued", "execution_profile": "safe"},
        {"run_id": "2", "status": "awaiting_approval", "execution_profile": "owner"},
    ]

    assert [run["run_id"] for run in filter_runs(runs, status="queued")] == ["1"]
    assert [run["run_id"] for run in filter_runs(runs, status="awaiting_approval")] == ["2"]


def test_compact_step_inspector_limits_result_to_240_characters() -> None:
    inspected = compact_step_inspector(
        {
            "run_id": "run-1",
            "execution_profile": "safe",
            "steps": [{"id": 1, "status": "completed", "result": "x" * 400}],
            "artifacts": [],
        }
    )

    assert inspected is not None
    assert set(inspected) == {"run_id", "profile", "step_count", "artifact_count", "steps"}
    assert inspected["profile"] == "safe"
    assert len(inspected["steps"][0]["result"]) == 240
    assert inspected["steps"][0]["result"].endswith("…")
    assert inspected["steps"][0]["result_preview"] == inspected["steps"][0]["result"]
