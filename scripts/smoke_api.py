#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int | None
    detail: str


def request_json(base_url: str, path: str, api_key: str | None = None, expected_status: int = 200) -> CheckResult:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    except urllib.error.URLError as exc:
        return CheckResult(path, False, None, f"connection_error: {exc}")

    ok = status_code == expected_status
    detail = "ok" if ok else f"expected {expected_status}, got {status_code}: {body[:300]}"
    if ok and body:
        try:
            json.loads(body)
        except json.JSONDecodeError:
            detail = "response_not_json"
            ok = False
    return CheckResult(path, ok, status_code, detail)


def request_html(base_url: str, path: str, api_key: str | None = None, expected_status: int = 200) -> CheckResult:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "text/html"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    except urllib.error.URLError as exc:
        return CheckResult(path, False, None, f"connection_error: {exc}")

    ok = status_code == expected_status and "<html" in body.lower()
    detail = "ok" if ok else f"expected html status {expected_status}, got {status_code}: {body[:300]}"
    return CheckResult(path, ok, status_code, detail)


def run_smoke_checks(base_url: str, api_key: str) -> list[CheckResult]:
    checks = [
        request_json(base_url, "/health", expected_status=200),
        request_json(base_url, "/status", expected_status=401),
        request_json(base_url, "/version", api_key=api_key, expected_status=200),
        request_json(base_url, "/status", api_key=api_key, expected_status=200),
        request_json(base_url, "/metrics", api_key=api_key, expected_status=200),
        request_json(base_url, "/diagnostics/v2", api_key=api_key, expected_status=200),
        request_json(base_url, "/runs", api_key=api_key, expected_status=200),
        request_json(base_url, "/approvals", api_key=api_key, expected_status=200),
        request_json(base_url, "/approvals/v2", api_key=api_key, expected_status=200),
        request_json(base_url, "/profiles/active", api_key=api_key, expected_status=200),
        request_json(base_url, "/profiles/explain/shell__run", api_key=api_key, expected_status=200),
        request_json(base_url, "/release/readiness", api_key=api_key, expected_status=200),
        request_html(base_url, "/dashboard/v2", api_key=api_key, expected_status=200),
    ]
    return checks


def print_results(results: list[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        code = "-" if result.status_code is None else str(result.status_code)
        print(f"{status:4} {result.name:<{width}} status={code} {result.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a running Velocity Claw API service.")
    parser.add_argument("--base-url", default=os.getenv("VELOCITY_CLAW_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("VELOCITY_CLAW_API_KEY") or os.getenv("API_KEY"))
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Set VELOCITY_CLAW_API_KEY/API_KEY or pass --api-key.", file=sys.stderr)
        return 2

    results = run_smoke_checks(args.base_url, args.api_key)
    print_results(results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
