from __future__ import annotations

import errno
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.auth import (
    apply_login,
    count_users,
    find_user_by_username,
    hash_password,
    normalize_username,
    permissions_for_role,
    require_admin_user,
    require_authenticated_user,
    resolve_next_path,
    verify_password,
)
from h15hub.configuration import read_config_text, save_config_text
from h15hub.database import get_db
from h15hub.models.board import BoardCard, BoardGroup, BoardProject
from h15hub.models.user import User, UserRole

router = APIRouter(tags=["auth", "admin"])


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    permissions: list[str]
    created_at: datetime


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    next_path: str | None = Field(default=None, max_length=512)


class SetupRequest(AuthRequest):
    display_name: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    user: UserResponse
    redirect_to: str


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    role: UserRole = UserRole.MEMBER
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    role: UserRole | None = None
    is_active: bool | None = None


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RuntimeConfigResponse(BaseModel):
    path: str
    content: str
    requires_restart: bool = True


class RuntimeConfigUpdate(BaseModel):
    content: str = Field(min_length=1)


def _serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        permissions=permissions_for_role(user.role),
        created_at=user.created_at,
    )


def _clean_name(name: str, *, field_name: str) -> str:
    value = name.strip()
    if not value:
        raise HTTPException(status_code=422, detail=f"{field_name} darf nicht leer sein")
    return value


def _hash_password_or_422(password: str) -> tuple[str, str]:
    try:
        return hash_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _config_io_error_to_500(exc: OSError, *, action: str) -> HTTPException:
    detail = f"Konfiguration konnte nicht {action} werden: {exc.strerror or exc}"
    if exc.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
        detail += ". Bitte den Config-Mount schreibbar (rw) einbinden."
    return HTTPException(status_code=500, detail=detail)


async def _ensure_unique_group_name(db: AsyncSession, name: str, *, exclude_group_id: int | None = None) -> None:
    stmt = select(BoardGroup).where(func.lower(BoardGroup.name) == name.lower())
    if exclude_group_id is not None:
        stmt = stmt.where(BoardGroup.id != exclude_group_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Gruppe existiert bereits")


async def _ensure_unique_username(db: AsyncSession, username: str, *, exclude_user_id: int | None = None) -> None:
    stmt = select(User).where(func.lower(User.username) == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Benutzername existiert bereits")


async def _ensure_admin_guardrails(
    db: AsyncSession,
    *,
    actor: User,
    target_user: User,
    new_role: UserRole,
    new_is_active: bool,
) -> None:
    if actor.id == target_user.id and not new_is_active:
        raise HTTPException(status_code=400, detail="Der eigene Account kann nicht deaktiviert werden")

    if target_user.role == UserRole.ADMIN and target_user.is_active and (
        new_role != UserRole.ADMIN or not new_is_active
    ):
        result = await db.execute(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
                User.id != target_user.id,
            )
        )
        if int(result.scalar_one()) == 0:
            raise HTTPException(status_code=400, detail="Mindestens ein aktiver Admin muss erhalten bleiben")


@router.post("/api/auth/setup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def setup_initial_admin(
    data: SetupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    if await count_users(db) > 0:
        raise HTTPException(status_code=409, detail="Es existiert bereits ein Benutzerkonto")

    username = normalize_username(data.username)
    display_name = _clean_name(data.display_name, field_name="Name")
    await _ensure_unique_username(db, username)
    password_salt, password_hash = _hash_password_or_422(data.password)

    user = User(
        username=username,
        display_name=display_name,
        password_salt=password_salt,
        password_hash=password_hash,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    apply_login(request, user)

    return AuthResponse(
        user=_serialize_user(user),
        redirect_to=resolve_next_path(data.next_path, "/admin"),
    )


@router.post("/api/auth/login", response_model=AuthResponse)
async def login(
    data: AuthRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    if await count_users(db) == 0:
        raise HTTPException(status_code=409, detail="Bitte zuerst ein Admin-Konto einrichten")

    user = await find_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort ist falsch")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Dieses Konto ist deaktiviert")

    apply_login(request, user)
    fallback = "/admin" if user.role == UserRole.ADMIN else "/"
    return AuthResponse(user=_serialize_user(user), redirect_to=resolve_next_path(data.next_path, fallback))


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> None:
    request.session.clear()


@router.get("/api/auth/me", response_model=UserResponse)
async def me(current_user: User = Depends(require_authenticated_user)) -> UserResponse:
    return _serialize_user(current_user)


@router.get("/api/admin/users", response_model=list[UserResponse])
async def list_users(_admin: User = Depends(require_admin_user), db: AsyncSession = Depends(get_db)) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.display_name, User.username))
    return [_serialize_user(user) for user in result.scalars().all()]


@router.get("/api/admin/config", response_model=RuntimeConfigResponse)
async def get_runtime_config(_admin: User = Depends(require_admin_user)) -> RuntimeConfigResponse:
    try:
        config_path, content = read_config_text()
    except OSError as exc:
        raise _config_io_error_to_500(exc, action="gelesen") from exc

    return RuntimeConfigResponse(path=str(config_path), content=content)


@router.patch("/api/admin/config", response_model=RuntimeConfigResponse)
async def update_runtime_config(
    data: RuntimeConfigUpdate,
    _admin: User = Depends(require_admin_user),
) -> RuntimeConfigResponse:
    try:
        config_path = save_config_text(data.content)
        content = config_path.read_text(encoding="utf-8")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise _config_io_error_to_500(exc, action="gespeichert") from exc

    return RuntimeConfigResponse(path=str(config_path), content=content)


@router.post("/api/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    username = normalize_username(data.username)
    display_name = _clean_name(data.display_name, field_name="Name")
    await _ensure_unique_username(db, username)
    password_salt, password_hash = _hash_password_or_422(data.password)

    user = User(
        username=username,
        display_name=display_name,
        password_salt=password_salt,
        password_hash=password_hash,
        role=data.role,
        is_active=data.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _serialize_user(user)


@router.patch("/api/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    new_role = data.role or user.role
    new_is_active = data.is_active if data.is_active is not None else user.is_active
    await _ensure_admin_guardrails(
        db,
        actor=admin,
        target_user=user,
        new_role=new_role,
        new_is_active=new_is_active,
    )

    if "username" in data.model_fields_set and data.username is not None:
        username = normalize_username(data.username)
        await _ensure_unique_username(db, username, exclude_user_id=user.id)
        user.username = username
    if "display_name" in data.model_fields_set and data.display_name is not None:
        user.display_name = _clean_name(data.display_name, field_name="Name")
    if "role" in data.model_fields_set and data.role is not None:
        user.role = data.role
    if "is_active" in data.model_fields_set and data.is_active is not None:
        user.is_active = data.is_active
    if "password" in data.model_fields_set and data.password is not None:
        user.password_salt, user.password_hash = _hash_password_or_422(data.password)

    await db.commit()
    await db.refresh(user)
    return _serialize_user(user)


@router.get("/api/admin/groups", response_model=list[GroupResponse])
async def list_admin_groups(_admin: User = Depends(require_admin_user), db: AsyncSession = Depends(get_db)) -> list[BoardGroup]:
    result = await db.execute(select(BoardGroup).order_by(BoardGroup.name))
    return list(result.scalars().all())


@router.post("/api/admin/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BoardGroup:
    name = _clean_name(data.name, field_name="Gruppenname")
    await _ensure_unique_group_name(db, name)
    group = BoardGroup(name=name)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/api/admin/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BoardGroup:
    group = await db.get(BoardGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    name = _clean_name(data.name, field_name="Gruppenname")
    await _ensure_unique_group_name(db, name, exclude_group_id=group.id)
    group.name = name
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/api/admin/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    group = await db.get(BoardGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    project_ids = select(BoardProject.id).where(BoardProject.group_id == group_id)
    await db.execute(delete(BoardCard).where(BoardCard.project_id.in_(project_ids)))
    await db.execute(delete(BoardProject).where(BoardProject.group_id == group_id))
    await db.delete(group)
    await db.commit()