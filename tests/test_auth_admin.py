from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from h15hub.api.admin import router as admin_router
from h15hub.database import Base, get_db


@pytest.fixture
async def admin_client(tmp_path):
    db_file = tmp_path / "auth.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(admin_router)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    await engine.dispose()


def test_admin_endpoints_require_authentication(admin_client):
    response = admin_client.get("/api/admin/users")
    assert response.status_code == 401


def test_setup_creates_admin_and_persists_session(admin_client):
    response = admin_client.post(
        "/api/auth/setup",
        json={
            "username": "Admin",
            "display_name": "Werkstatt Admin",
            "password": "supersecret123",
            "next_path": "/boards",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert data["redirect_to"] == "/boards"

    me_response = admin_client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["display_name"] == "Werkstatt Admin"


def test_member_login_redirects_to_dashboard(admin_client):
    setup_response = admin_client.post(
        "/api/auth/setup",
        json={
            "username": "admin",
            "display_name": "Admin",
            "password": "supersecret123",
        },
    )
    assert setup_response.status_code == 201

    create_response = admin_client.post(
        "/api/admin/users",
        json={
            "username": "member1",
            "display_name": "Mitglied Eins",
            "password": "membersecret123",
            "role": "member",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201

    logout_response = admin_client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    login_response = admin_client.post(
        "/api/auth/login",
        json={
            "username": "member1",
            "password": "membersecret123",
        },
    )
    assert login_response.status_code == 200
    assert login_response.json()["redirect_to"] == "/"


def test_last_admin_cannot_deactivate_self(admin_client):
    setup_response = admin_client.post(
        "/api/auth/setup",
        json={
            "username": "admin",
            "display_name": "Admin",
            "password": "supersecret123",
        },
    )
    assert setup_response.status_code == 201
    user_id = setup_response.json()["user"]["id"]

    update_response = admin_client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False},
    )
    assert update_response.status_code == 400
    assert "nicht deaktiviert" in update_response.json()["detail"]


def test_admin_can_read_and_update_runtime_config(admin_client, tmp_path, monkeypatch):
    config_file = tmp_path / "config" / "config.yaml"
    monkeypatch.setenv("H15HUB_CONFIG", str(config_file))

    setup_response = admin_client.post(
        "/api/auth/setup",
        json={
            "username": "admin",
            "display_name": "Admin",
            "password": "supersecret123",
        },
    )
    assert setup_response.status_code == 201

    get_response = admin_client.get("/api/admin/config")
    assert get_response.status_code == 200
    assert get_response.json()["path"] == str(config_file)
    assert "devices: {}" in get_response.json()["content"]
    assert config_file.exists()

    new_config = """app:
  title: \"Test Hub\"
devices:
  printer:
    adapter: laserprinter
    url: ipp://192.168.1.50/ipp/print
automations: []
"""
    update_response = admin_client.patch("/api/admin/config", json={"content": new_config})
    assert update_response.status_code == 200
    assert update_response.json()["content"] == new_config
    assert config_file.read_text(encoding="utf-8") == new_config


def test_admin_rejects_invalid_runtime_config(admin_client, tmp_path, monkeypatch):
    monkeypatch.setenv("H15HUB_CONFIG", str(tmp_path / "config" / "config.yaml"))

    setup_response = admin_client.post(
        "/api/auth/setup",
        json={
            "username": "admin",
            "display_name": "Admin",
            "password": "supersecret123",
        },
    )
    assert setup_response.status_code == 201

    response = admin_client.patch("/api/admin/config", json={"content": "- invalid\n- list\n"})
    assert response.status_code == 422
    assert "YAML-Objekt" in response.json()["detail"]