from pathlib import Path
from types import SimpleNamespace

from velocity_claw.memory.run_profiles import install_run_profile_tracking


class DisabledMemory:
    enabled = False

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self.created = []

    def create_run(self, task: str) -> str:
        run_id = f"run-{len(self.created) + 1}"
        self.created.append((run_id, task))
        return run_id

    def list_recent_runs(self, limit: int = 20):
        return [
            {"run_id": run_id, "task": task, "status": "completed"}
            for run_id, task in self.created[-limit:]
        ]

    def load_run(self, run_id: str):
        return {"run_id": run_id, "task": "disabled", "status": "completed"}


class ReadOnlyMemory:
    def list_recent_runs(self, limit: int = 20):
        return [
            {
                "run_id": "read-only-1",
                "task": "Render dashboard",
                "status": "completed",
            }
        ][:limit]


def test_disabled_memory_does_not_create_profile_database(tmp_path: Path):
    db_path = tmp_path / "disabled-memory.db"
    memory = DisabledMemory(db_path)
    agent = SimpleNamespace(
        memory=memory,
        settings=SimpleNamespace(execution_profile="owner"),
    )

    store = install_run_profile_tracking(agent)
    run_id = memory.create_run("Do not persist")
    runs = memory.list_recent_runs(limit=10)
    loaded = memory.load_run(run_id)

    assert store.enabled is False
    assert db_path.exists() is False
    assert runs[0]["execution_profile"] == "unknown"
    assert loaded["execution_profile"] == "unknown"
    assert store.list_profiles() == []


def test_read_only_memory_backend_remains_dashboard_compatible():
    memory = ReadOnlyMemory()
    agent = SimpleNamespace(memory=memory)

    store = install_run_profile_tracking(agent)
    runs = memory.list_recent_runs(limit=10)

    assert store.enabled is False
    assert runs == [
        {
            "run_id": "read-only-1",
            "task": "Render dashboard",
            "status": "completed",
            "execution_profile": "unknown",
        }
    ]
    assert not hasattr(memory, "create_run")
    assert not hasattr(memory, "load_run")
