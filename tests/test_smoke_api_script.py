from scripts import smoke_api
from scripts.smoke_api import CheckResult, main, print_results, run_smoke_checks


def test_smoke_api_main_requires_api_key(monkeypatch):
    monkeypatch.delenv("VELOCITY_CLAW_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["smoke_api.py"])

    assert main() == 2


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
    assert ("json", "/status", "secret", 200) in calls
    assert ("json", "/diagnostics/v2", "secret", 200) in calls
    assert ("html", "/dashboard/v2", "secret", 200) in calls
