from pathlib import Path


API_DOC = Path("docs/API.md")
README = Path("README.md")
DEPLOYMENT = Path("docs/DEPLOYMENT.md")


def test_api_doc_lists_v2_operator_endpoints():
    content = API_DOC.read_text(encoding="utf-8")

    required = [
        "/version",
        "/dashboard/v2",
        "/diagnostics/v2",
        "/runs/{run_id}/detail/v2",
        "/runs/{run_id}/artifacts/v2",
        "/approvals/v2/{run_id}/{step_id}",
        "/approvals/v2/{run_id}/{step_id}/approve",
        "/approvals/v2/{run_id}/{step_id}/reject",
        "/profiles/explain/{tool_name}",
    ]
    for endpoint in required:
        assert endpoint in content


def test_api_doc_documents_auth_headers_and_error_behavior():
    content = API_DOC.read_text(encoding="utf-8")

    assert "X-API-Key" in content
    assert "Authorization: Bearer" in content
    assert "401" in content
    assert "409" in content
    assert "503" in content


def test_primary_docs_link_to_api_guide():
    assert "docs/API.md" in README.read_text(encoding="utf-8")
    assert "docs/API.md" in DEPLOYMENT.read_text(encoding="utf-8")
