from scripts.smoke_api import CheckResult, main, print_results


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
