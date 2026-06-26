from types import SimpleNamespace

from velocity_claw.core.agent import VelocityClawAgent
from velocity_claw.tools.fs import FileSystemTool


def build_fs(tmp_path):
    settings = SimpleNamespace(workspace_root=str(tmp_path), max_file_size=1024 * 1024)
    return FileSystemTool(settings)


def test_write_returns_unified_diff_before_persisted_content(tmp_path):
    fs = build_fs(tmp_path)

    result = fs.write("sample.txt", "hello\n")

    assert result["status"] == "completed"
    assert result["action"] == "fs.write"
    assert result["changed"] is True
    assert "--- a/sample.txt" in result["diff"]
    assert "+++ b/sample.txt" in result["diff"]
    assert "+hello" in result["diff"]
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "hello\n"


def test_append_and_replace_return_step_ready_diffs(tmp_path):
    fs = build_fs(tmp_path)
    (tmp_path / "sample.txt").write_text("one\n", encoding="utf-8")

    appended = fs.append("sample.txt", "two\n")
    replaced = fs.replace("sample.txt", "two", "second")

    assert appended["action"] == "fs.append"
    assert "+two" in appended["diff"]
    assert replaced["action"] == "fs.replace"
    assert "-two" in replaced["diff"]
    assert "+second" in replaced["diff"]
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "one\nsecond\n"


def test_no_op_write_is_reported_without_diff(tmp_path):
    fs = build_fs(tmp_path)
    (tmp_path / "same.txt").write_text("same\n", encoding="utf-8")

    result = fs.write("same.txt", "same\n")

    assert result["changed"] is False
    assert result["diff"] == ""
    assert result["bytes_before"] == result["bytes_after"]


def test_diff_result_is_persisted_as_run_step_artifact():
    saved = []

    class FakeMemory:
        def save_artifact(self, run_id, name, content, step_id=None, artifact_type="text"):
            saved.append(
                {
                    "run_id": run_id,
                    "name": name,
                    "content": content,
                    "step_id": step_id,
                    "artifact_type": artifact_type,
                }
            )

    fake_agent = SimpleNamespace(memory=FakeMemory())
    VelocityClawAgent._persist_artifacts(
        fake_agent,
        "run-1",
        {
            "id": 7,
            "result": {
                "status": "completed",
                "action": "fs.replace",
                "diff": "--- a/example.py\n+++ b/example.py\n-old\n+new\n",
            },
        },
    )

    assert saved == [
        {
            "run_id": "run-1",
            "name": "step_7_diff",
            "content": "--- a/example.py\n+++ b/example.py\n-old\n+new\n",
            "step_id": 7,
            "artifact_type": "diff",
        }
    ]
