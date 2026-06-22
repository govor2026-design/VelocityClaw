from velocity_claw.api.dashboard_v2 import render_dashboard_v2


def render(runs):
    return render_dashboard_v2(
        execution_profile="safe",
        safe_mode=True,
        trusted_mode=False,
        release_state={"readiness": "ready", "score": 5, "total_checks": 5},
        console={"queue": {"running": 0, "failed": 0}, "approvals": {"pending": 0}},
        recent_runs=runs,
        approvals=[],
        queue_jobs=[],
        metrics={"tasks_total": 2},
        provider_observability={"summary": {"failed_routes": 0}},
        provider_health={},
        last_failed=None,
    )


def test_dashboard_renders_status_and_profile_filters():
    html = render(
        [
            {
                "run_id": "run-safe",
                "task": "Successful task",
                "status": "completed",
                "execution_profile": "safe",
                "created_at": "2026-06-22T08:00:00",
            },
            {
                "run_id": "run-dev",
                "task": "Failed task",
                "status": "failed",
                "execution_profile": "dev",
                "created_at": "2026-06-22T08:01:00",
            },
        ]
    )

    assert "id='run-status-filter'" in html
    assert "id='run-profile-filter'" in html
    assert "<option value='completed'>completed</option>" in html
    assert "<option value='failed'>failed</option>" in html
    assert "<option value='dev'>dev</option>" in html
    assert "<option value='safe'>safe</option>" in html
    assert "data-status='completed' data-profile='safe'" in html
    assert "data-status='failed' data-profile='dev'" in html
    assert "Visible: <b id='run-visible-count'>2</b> / 2" in html
    assert "No runs match the selected status and profile." in html


def test_dashboard_links_run_ids_to_html_inspector():
    html = render(
        [
            {
                "run_id": "run-123",
                "task": "Inspect artifacts",
                "status": "completed",
                "execution_profile": "owner",
                "created_at": "2026-06-22T08:00:00",
            }
        ]
    )

    assert "href='/runs/run-123/view'" in html
    assert ">inspect</a>" in html
    assert "detail json" in html
    assert "artifacts json" in html


def test_dashboard_escapes_run_content_and_handles_empty_state():
    html = render(
        [
            {
                "run_id": "unsafe<script>",
                "task": "<img src=x onerror=alert(1)>",
                "status": "running",
                "execution_profile": "unknown",
                "created_at": None,
            }
        ]
    )

    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "unsafe&lt;script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html

    empty_html = render([])
    assert "No runs recorded yet." in empty_html
    assert "Visible: <b id='run-visible-count'>0</b> / 0" in empty_html
