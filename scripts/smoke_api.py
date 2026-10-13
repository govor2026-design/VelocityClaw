#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int | None
    detail: str
    payload: Any | None = None


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
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return CheckResult(path, False, None, f"connection_error: {exc}")

    payload: Any | None = None
    ok = status_code == expected_status
    detail = "ok" if ok else f"expected {expected_status}, got {status_code}: {body[:300]}"
    if ok:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            detail = "response_not_json"
            ok = False
    return CheckResult(path, ok, status_code, detail, payload)


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
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return CheckResult(path, False, None, f"connection_error: {exc}")

    ok = status_code == expected_status and "<html" in body.lower()
    detail = "ok" if ok else f"expected html status {expected_status}, got {status_code}: {body[:300]}"
    return CheckResult(path, ok, status_code, detail)


def validate_deployment_runtime(
    version_result: CheckResult,
    *,
    expected_version: str | None = None,
    require_safe_runtime: bool = False,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    payload = version_result.payload if isinstance(version_result.payload, dict) else {}
    if expected_version:
        actual_version = payload.get("version")
        checks.append(
            CheckResult(
                "version_match",
                version_result.ok and actual_version == expected_version,
                version_result.status_code,
                "ok" if actual_version == expected_version else f"expected {expected_version}, got {actual_version}",
            )
        )

    if require_safe_runtime:
        runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
        expected = {
            "env": "production",
            "execution_profile": "safe",
            "safe_mode": True,
            "trusted_mode": False,
        }
        mismatches = [
            f"{key}={runtime.get(key)!r}"
            for key, value in expected.items()
            if runtime.get(key) != value
        ]
        checks.append(
            CheckResult(
                "runtime_safety",
                version_result.ok and not mismatches,
                version_result.status_code,
                "ok" if not mismatches else "unexpected " + ", ".join(mismatches),
            )
        )
    return checks


def run_smoke_checks(
    base_url: str,
    api_key: str,
    *,
    expected_version: str | None = None,
    require_safe_runtime: bool = False,
) -> list[CheckResult]:
    version_result = request_json(base_url, "/version", api_key=api_key, expected_status=200)
    results = [
        request_json(base_url, "/health", expected_status=200),
        request_json(base_url, "/status", expected_status=401),
        version_result,
        request_json(base_url, "/status", api_key=api_key, expected_status=200),
        request_json(base_url, "/metrics", api_key=api_key, expected_status=200),
        request_json(base_url, "/diagnostics/v2", api_key=api_key, expected_status=200),
        request_json(base_url, "/queue/v2/runtime", api_key=api_key, expected_status=200),
        request_json(base_url, "/runs", api_key=api_key, expected_status=200),
        request_json(base_url, "/approvals", api_key=api_key, expected_status=200),
        request_json(base_url, "/approvals/v2", api_key=api_key, expected_status=200),
        request_json(base_url, "/profiles/active", api_key=api_key, expected_status=200),
        request_json(base_url, "/profiles/explain/shell__run", api_key=api_key, expected_status=200),
        request_json(base_url, "/release/readiness", api_key=api_key, expected_status=200),
        request_html(base_url, "/dashboard/v2", api_key=api_key, expected_status=200),
    ]
    results[3:3] = validate_deployment_runtime(
        version_result,
        expected_version=expected_version,
        require_safe_runtime=require_safe_runtime,
    )
    return results


def print_results(results: list[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        code = "-" if result.status_code is None else str(result.status_code)
        print(f"{status:4} {result.name:<{width}} status={code} {result.detail}")


def build_report(results: list[CheckResult]) -> dict[str, Any]:
    return {
        "status": "ok" if all(result.ok for result in results) else "failed",
        "checks": [
            {
                "name": result.name,
                "ok": result.ok,
                "status_code": result.status_code,
                "detail": result.detail,
            }
            for result in results
        ],
    }


def resolve_expected_version() -> str | None:
    configured = os.getenv("VELOCITY_CLAW_EXPECTED_VERSION")
    if configured and configured.strip():
        return configured.strip()
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8").strip()
        return value or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a running Velocity Claw API service.")
    parser.add_argument("--base-url", default=os.getenv("VELOCITY_CLAW_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("VELOCITY_CLAW_API_KEY") or os.getenv("API_KEY"))
    parser.add_argument("--expected-version", default=resolve_expected_version())
    parser.add_argument("--allow-unsafe-runtime", action="store_true", help="Skip production safe-profile assertions")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable smoke report")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Set VELOCITY_CLAW_API_KEY/API_KEY or pass --api-key.", file=sys.stderr)
        return 2

    results = run_smoke_checks(
        args.base_url,
        args.api_key,
        expected_version=args.expected_version,
        require_safe_runtime=not args.allow_unsafe_runtime,
    )
    if args.json:
        print(json.dumps(build_report(results), ensure_ascii=False, indent=2))
    else:
        print_results(results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
