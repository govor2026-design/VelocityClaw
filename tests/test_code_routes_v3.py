from pathlib import Path

from velocity_claw.config.settings import Settings
from velocity_claw.tools.code_nav import CodeNavigationTool


def build_tool(tmp_path: Path) -> CodeNavigationTool:
    return CodeNavigationTool(Settings(env="test", workspace_root=str(tmp_path)))


def write_routes(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text(
        """from fastapi import APIRouter
from flask import Flask
router = APIRouter()
app = Flask(__name__)

@router.get('/users/{user_id}')
def get_user(user_id):
    return user_id

@router.post('/users')
async def create_user():
    return {'created': True}

@app.route('/health', methods=['GET', 'HEAD'])
def health():
    return 'ok'
""",
        encoding="utf-8",
    )
    (tmp_path / "urls.py").write_text(
        """from django.urls import path, re_path
from .views import item_detail, search
urlpatterns = [
    path('items/<int:item_id>/', item_detail),
    re_path(r'^search/$', search),
]
""",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.py").write_text(
        "@app.get('/ignored')\ndef ignored():\n    return None\n",
        encoding="utf-8",
    )


def test_routes_cover_fastapi_flask_and_django(tmp_path: Path):
    write_routes(tmp_path)
    routes = build_tool(tmp_path).find_routes()
    by_route = {item["route"]: item for item in routes}

    assert set(by_route) == {
        "/users/{user_id}",
        "/users",
        "/health",
        "items/<int:item_id>/",
        "^search/$",
    }
    assert by_route["/users/{user_id}"]["methods"] == ["GET"]
    assert by_route["/users"]["is_async"] is True
    assert by_route["/health"]["methods"] == ["GET", "HEAD"]
    assert by_route["/health"]["framework"] == "flask"
    assert by_route["items/<int:item_id>/"]["framework"] == "django"
    assert by_route["items/<int:item_id>/"]["methods"] == ["ANY"]
    assert "/ignored" not in by_route


def test_route_filters_by_method_path_and_route(tmp_path: Path):
    write_routes(tmp_path)
    tool = build_tool(tmp_path)

    post_routes = tool.find_routes(path="api.py", method="POST")
    user_routes = tool.find_routes(route="users")
    django_get = tool.find_routes(path="urls.py", method="GET")

    assert [item["route"] for item in post_routes] == ["/users"]
    assert {item["route"] for item in user_routes} == {"/users", "/users/{user_id}"}
    assert {item["route"] for item in django_get} == {
        "items/<int:item_id>/",
        "^search/$",
    }
