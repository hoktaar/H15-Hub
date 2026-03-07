from __future__ import annotations

import hashlib
import hmac
import secrets
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.database import get_db
from h15hub.models.user import User, UserRole

MIN_PASSWORD_LENGTH = 8
PASSWORD_ITERATIONS = 390000

ROLE_PERMISSIONS = {
    UserRole.ADMIN: {"manage_groups", "manage_members", "use_boards", "use_devices", "use_bookings"},
    UserRole.MEMBER: {"use_boards", "use_devices", "use_bookings"},
}


def normalize_username(username: str) -> str:
    return username.strip().lower()


def permissions_for_role(role: UserRole) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein")
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, password_hash: str) -> bool:
    _, computed_hash = hash_password(password, salt_hex)
    return hmac.compare_digest(computed_hash, password_hash)


def resolve_next_path(next_path: str | None, fallback: str = "/") -> str:
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return fallback


def build_login_redirect(request: Request) -> RedirectResponse:
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=f"/login?next={quote(target, safe='/?=&')}", status_code=303)


async def count_users(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(User.id)))
    return int(result.scalar_one())


async def find_user_by_username(db: AsyncSession, username: str) -> User | None:
    normalized = normalize_username(username)
    result = await db.execute(select(User).where(func.lower(User.username) == normalized))
    return result.scalar_one_or_none()


async def get_current_user_from_request(request: Request, db: AsyncSession) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        return None
    return user


async def require_authenticated_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_current_user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anmeldung erforderlich")
    return user


async def require_admin_user(user: User = Depends(require_authenticated_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Adminrechte erforderlich")
    return user


async def ensure_page_user(request: Request, db: AsyncSession) -> User | RedirectResponse:
    if await count_users(db) == 0:
        return RedirectResponse(url="/setup", status_code=303)
    user = await get_current_user_from_request(request, db)
    if not user:
        return build_login_redirect(request)
    return user


async def ensure_page_admin(request: Request, db: AsyncSession) -> User | RedirectResponse:
    user = await ensure_page_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Adminrechte erforderlich")
    return user


def apply_login(request: Request, user: User) -> None:
    request.session.clear()
    request.session["user_id"] = user.id