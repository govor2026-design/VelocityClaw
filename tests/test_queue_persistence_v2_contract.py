from pathlib import Path


def test_queue_persistence_v2_contract_files_exist():
    assert Path("docs/QUEUE.md").exists()
    assert Path("velocity_claw/core/queue.py").exists()
