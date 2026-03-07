from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from h15hub.api.admin import router as admin_router
from h15hub.api.boards import router as board_router
from h15hub.database import Base, get_db


@pytest.fixture
async def board_client(tmp_path):
    db_file = tmp_path / "boards.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(admin_router)
    app.include_router(board_router)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        setup_response = client.post(
            "/api/auth/setup",
            json={
                "username": "admin",
                "display_name": "Werkstatt Admin",
                "password": "supersecret123",
            },
        )
        assert setup_response.status_code == 201
        yield client

    await engine.dispose()


def create_group(client: TestClient, name: str = "Laser-Team") -> dict:
    response = client.post("/api/boards/groups", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_board_endpoints_require_authentication(tmp_path):
    db_file = tmp_path / "boards-auth.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")

    async def prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio
    asyncio.run(prepare())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(board_router)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        response = client.get("/api/boards/groups")
        assert response.status_code == 401

    asyncio.run(engine.dispose())


def test_create_group_and_card(board_client):
    group = create_group(board_client)

    response = board_client.post(
        f"/api/boards/{group['id']}/cards",
        json={
            "title": "Spiegel reinigen",
            "description": "Vor der offenen Werkstatt prüfen",
            "assignee": "Alex",
            "column": "backlog",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["group_id"] == group["id"]
    assert data["title"] == "Spiegel reinigen"
    assert data["position"] == 0

    list_response = board_client.get(f"/api/boards/{group['id']}/cards")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_move_card_within_and_between_columns(board_client):
    group = create_group(board_client, "3D-Druck")

    first = board_client.post(
        f"/api/boards/{group['id']}/cards",
        json={"title": "Düse prüfen", "column": "backlog"},
    ).json()
    second = board_client.post(
        f"/api/boards/{group['id']}/cards",
        json={"title": "Filament trocknen", "column": "backlog"},
    ).json()

    move_same_column = board_client.patch(
        f"/api/boards/cards/{second['id']}",
        json={"column": "backlog", "position": 0},
    )
    assert move_same_column.status_code == 200

    cards = board_client.get(f"/api/boards/{group['id']}/cards").json()
    backlog_ids = [card["id"] for card in cards if card["column"] == "backlog"]
    assert backlog_ids == [second["id"], first["id"]]

    move_other_column = board_client.patch(
        f"/api/boards/cards/{first['id']}",
        json={"column": "done", "position": 0},
    )
    assert move_other_column.status_code == 200

    cards = board_client.get(f"/api/boards/{group['id']}/cards").json()
    backlog_positions = [(card["id"], card["position"]) for card in cards if card["column"] == "backlog"]
    done_positions = [(card["id"], card["position"]) for card in cards if card["column"] == "done"]
    assert backlog_positions == [(second["id"], 0)]
    assert done_positions == [(first["id"], 0)]


def test_delete_card_reorders_remaining_cards(board_client):
    group = create_group(board_client, "Elektronik")

    first = board_client.post(
        f"/api/boards/{group['id']}/cards",
        json={"title": "Lötstation aufräumen", "column": "in_progress"},
    ).json()
    second = board_client.post(
        f"/api/boards/{group['id']}/cards",
        json={"title": "Bauteile nachfüllen", "column": "in_progress"},
    ).json()

    delete_response = board_client.delete(f"/api/boards/cards/{first['id']}")
    assert delete_response.status_code == 204

    cards = board_client.get(f"/api/boards/{group['id']}/cards").json()
    assert cards == [
        {
            "id": second["id"],
            "group_id": group["id"],
            "title": "Bauteile nachfüllen",
            "description": None,
            "assignee": None,
            "column": "in_progress",
            "position": 0,
        }
    ]