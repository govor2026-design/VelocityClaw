from scripts import smoke_api
from scripts.smoke_api import (
    CheckResult,
    build_report,
    main,
    print_results,
    run_smoke_checks,
)


class FakeResponse:
    def __init__(self, body: bytes, status_code: int = 200):
        self.body = body
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body

    def getcode(self):
        return self.status_code


def test_smoke_api_main_requires_api_key(monkeypatch):
    monkeypatch.delenv("VELOCITY_CLAW_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["smoke_api.py"])

    assert main() == 2


def test_smoke_api_rejects_empty_json_response(monkeypatch):
    monkeypatch.setattr(smoke_api.urllib.request, "urlopen", lambda request, timeout: FakeResponse(b""))

    result = smoke_api.request_json("http://127.0.0.1:8000", "/health")

    assert result.ok is False
    assert result.detail == "response_not_json"


def test_smoke_api_converts_timeout_to_failed_check(monkeypatch):
    def timeout(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(smoke_api.urllib.request, "urlopen", timeout)

    result = smoke_api.request_json("http://127.0.0.1:8000", "/health")

    assert result.ok is False
    assert result.status_code is None
    assert result.detail == "connection_error: timed out"


def test_smoke_api_print_results_reports_pass_and_fail(capsys):
    results = [
        CheckResult("/health", True, 200, "ok"),
        CheckResult("/status", False, 401, "expected 200"),
    ]

    print_results(results)
    output = capsys.readouterr().out

    assert "PASS /health" in output
    assert "FAIL /status" in output
    assert "status=200" in output
    assert "status=401" in output


def test_smoke_api_checks_expected_auth_and_operator_endpoints(monkeypatch):
    calls = []

    def fake_json(base_url, path, api_key=None, expected_status=200):
        calls.append(("json", path, api_key, expected_status))
        return CheckResult(path, True, expected_status, "ok")

    def fake_html(base_url, path, api_key=None, expected_status=200):
        calls.append(("html", path, api_key, expected_status))
        return CheckResult(path, True, expected_status, "ok")

    monkeypatch.setattr(smoke_api, "request_json", fake_json)
    monkeypatch.setattr(smoke_api, "request_html", fake_html)

    results = run_smoke_checks("http://127.0.0.1:8000", "secret")

    assert all(result.ok for result in results)
    assert ("json", "/health", None, 200) in calls
    assert ("json", "/status", None, 401) in calls
    assert ("json", "/version", "secret", 200) in calls
    assert ("json", "/status", "secret", 200) in calls
    assert ("json", "/diagnostics/v2", "secret", 200) in calls
    assert ("json", "/queue/v2/runtime", "secret", 200) in calls
    assert ("json", "/approvals/v2", "secret", 200) in calls
    assert ("html", "/dashboard/v2", "secret", 200) in calls


def test_smoke_api_enforces_version_and_safe_production_runtime(monkeypatch):
    def fake_json(base_url, path, api_key=None, expected_status=200):
        payload = None
        if path == "/version":
            payload = {
                "version": "0.2.4",
                "runtime": {
                    "env": "production",
                    "execution_profile": "safe",
                    "safe_mode": True,
                    "trusted_mode": False,
                },
            }
        return CheckResult(path, True, expected_status, "ok", payload)

    monkeypatch.setattr(smoke_api, "request_json", fake_json)
    monkeypatch.setattr(
        smoke_api,
        "request_html",
        lambda base_url, path, api_key=None, expected_status=200: CheckResult(
            path, True, expected_status, "ok"
        ),
    )

    results = run_smoke_checks(
        "http://127.0.0.1:8000",
        "secret",
        expected_version="0.2.4",
        require_safe_runtime=True,
    )

    by_name = {result.name: result for result in results}
    assert by_name["version_match"].ok is True
    assert by_name["runtime_safety"].ok is True


def test_smoke_api_reports_wrong_version_and_unsafe_runtime(monkeypatch):
    version = CheckResult(
        "/version",
        True,
        200,
        "ok",
        {
            "version": "0.2.3",
            "runtime": {
                "env": "development",
                "execution_profile": "owner",
                "safe_mode": False,
                "trusted_mode": True,
            },
        },
    )

    results = smoke_api.validate_deployment_runtime(
        version,
        expected_version="0.2.4",
        require_safe_runtime=True,
    )

    assert [result.ok for result in results] == [False, False]
    assert "expected 0.2.4" in results[0].detail
    assert "execution_profile='owner'" in results[1].detail


def test_smoke_api_builds_machine_readable_report():
    report = build_report(
        [
            CheckResult("/health", True, 200, "ok", {"status": "ok"}),
            CheckResult("runtime_safety", False, 200, "unexpected safe_mode=False"),
        ]
    )

    assert report["status"] == "failed"
    assert report["checks"][0] == {
        "name": "/health",
        "ok": True,
        "status_code": 200,
        "detail": "ok",
    }
    assert "payload" not in report["checks"][0]
