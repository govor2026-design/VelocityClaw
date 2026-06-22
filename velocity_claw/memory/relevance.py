from __future__ import annotations

import re
from typing import Any


STOP_WORDS = {
    "the", "and", "for", "from", "with", "into", "that", "this", "task", "run", "retry", "fix",
    "update", "add", "create", "implement", "для", "что", "это", "как", "или", "при", "про",
}


def tokenize(value: str | None) -> set[str]:
    text = (value or "").lower().replace("_", " ").replace("-", " ")
    tokens = re.findall(r"[a-zа-яё0-9.]{3,}", text, flags=re.IGNORECASE)
    return {token for token in tokens if token not in STOP_WORDS and not token.isdigit()}


def similarity(query: str, candidate: str) -> float:
    query_tokens = tokenize(query)
    candidate_tokens = tokenize(candidate)
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = query_tokens & candidate_tokens
    if not overlap:
        return 0.0
    coverage = len(overlap) / len(query_tokens)
    precision = len(overlap) / len(candidate_tokens)
    return round((coverage * 0.7) + (precision * 0.3), 4)


def compact_run(run: dict[str, Any], score: float | None = None) -> dict[str, Any]:
    payload = {
        "run_id": run.get("run_id"),
        "task": run.get("task"),
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
    }
    if score is not None:
        payload["similarity"] = score
    report = run.get("report") or {}
    if report.get("executive_summary"):
        payload["executive_summary"] = report["executive_summary"]
    forensics = run.get("forensics") or {}
    if forensics.get("failed_step"):
        payload["failed_step"] = forensics["failed_step"]
    return payload
