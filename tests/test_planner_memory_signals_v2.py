from velocity_claw.planner.planner import Planner


class DummyRouter:
    async def route(self, task_type, prompt):
        return {"text": '{"task":"x","steps":[]}'}


def make_prompt(signals):
    planner = Planner(DummyRouter())
    return planner._build_plan_prompt(
        "Fix queue cancellation",
        {
            "project_root": ".",
            "planning_context": {
                "project_facts": {"knowledge.queue.path": "velocity_claw/core/queue.py"},
                "recent_run_tasks": ["Repair queue worker cancellation"],
                "recent_failed_tasks": ["Queue worker cancellation regression"],
                "memory_signals_v2": signals,
            },
        },
    )


def test_prompt_includes_reuse_signal_and_prior_success_directive():
    prompt = make_prompt(
        {
            "related_run_count": 2,
            "reuse_prior_success": True,
            "inspect_before_edit": False,
        }
    )

    assert "Repo-aware memory signals" in prompt
    assert '"reuse_prior_success": true' in prompt
    assert "successful" in prompt.lower() or "успешного" in prompt.lower()


def test_prompt_includes_failure_inspection_directive():
    prompt = make_prompt(
        {
            "related_run_count": 3,
            "reuse_prior_success": False,
            "inspect_before_edit": True,
        }
    )

    assert '"inspect_before_edit": true' in prompt
    assert "inspection-first" in prompt
    assert "failure context" in prompt


def test_prompt_omits_v2_directives_when_signals_are_empty():
    prompt = make_prompt({})

    assert "Repo-aware memory signals" not in prompt
    assert '"inspect_before_edit": true' not in prompt
