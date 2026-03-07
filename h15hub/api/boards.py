from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.auth import require_authenticated_user
from h15hub.database import get_db
from h15hub.models.board import BoardCard, BoardCardColumn, BoardGroup

router = APIRouter(
    prefix="/api/boards",
    tags=["boards"],
    dependencies=[Depends(require_authenticated_user)],
)


class BoardGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class BoardGroupResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class BoardCardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    assignee: str | None = Field(default=None, max_length=128)
    column: BoardCardColumn = BoardCardColumn.BACKLOG


class BoardCardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    assignee: str | None = Field(default=None, max_length=128)
    column: BoardCardColumn | None = None
    position: int | None = Field(default=None, ge=0)


class BoardCardResponse(BaseModel):
    id: int
    group_id: int
    title: str
    description: str | None
    assignee: str | None
    column: BoardCardColumn
    position: int

    model_config = {"from_attributes": True}


async def _get_group_or_404(db: AsyncSession, group_id: int) -> BoardGroup:
    group = await db.get(BoardGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    return group


async def _get_card_or_404(db: AsyncSession, card_id: int) -> BoardCard:
    card = await db.get(BoardCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Karte nicht gefunden")
    return card


async def _cards_for_column(
    db: AsyncSession,
    group_id: int,
    column: BoardCardColumn,
    *,
    exclude_card_id: int | None = None,
) -> list[BoardCard]:
    stmt = select(BoardCard).where(
        BoardCard.group_id == group_id,
        BoardCard.column == column,
    )
    if exclude_card_id is not None:
        stmt = stmt.where(BoardCard.id != exclude_card_id)
    stmt = stmt.order_by(BoardCard.position, BoardCard.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _normalize_positions(cards: list[BoardCard]) -> None:
    for index, sibling in enumerate(cards):
        sibling.position = index


@router.get("/groups", response_model=list[BoardGroupResponse])
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[BoardGroup]:
    result = await db.execute(select(BoardGroup).order_by(BoardGroup.name))
    return list(result.scalars().all())


@router.post(
    "/groups",
    response_model=BoardGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    data: BoardGroupCreate,
    db: AsyncSession = Depends(get_db),
) -> BoardGroup:
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Gruppenname darf nicht leer sein")

    existing = await db.execute(
        select(BoardGroup).where(func.lower(BoardGroup.name) == name.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Gruppe existiert bereits")

    group = BoardGroup(name=name)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/{group_id}/cards", response_model=list[BoardCardResponse])
async def list_cards(
    group_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[BoardCard]:
    await _get_group_or_404(db, group_id)
    result = await db.execute(
        select(BoardCard)
        .where(BoardCard.group_id == group_id)
        .order_by(BoardCard.position, BoardCard.id)
    )
    return list(result.scalars().all())


@router.post(
    "/{group_id}/cards",
    response_model=BoardCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_card(
    group_id: int,
    data: BoardCardCreate,
    db: AsyncSession = Depends(get_db),
) -> BoardCard:
    await _get_group_or_404(db, group_id)

    siblings = await _cards_for_column(db, group_id, data.column)
    card = BoardCard(
        group_id=group_id,
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        assignee=data.assignee.strip() if data.assignee else None,
        column=data.column,
        position=len(siblings),
    )
    if not card.title:
        raise HTTPException(status_code=422, detail="Titel darf nicht leer sein")

    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.patch("/cards/{card_id}", response_model=BoardCardResponse)
async def update_card(
    card_id: int,
    data: BoardCardUpdate,
    db: AsyncSession = Depends(get_db),
) -> BoardCard:
    card = await _get_card_or_404(db, card_id)

    if "title" in data.model_fields_set and data.title is not None:
        title = data.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Titel darf nicht leer sein")
        card.title = title
    if "description" in data.model_fields_set:
        card.description = data.description.strip() if data.description else None
    if "assignee" in data.model_fields_set:
        card.assignee = data.assignee.strip() if data.assignee else None

    move_requested = "column" in data.model_fields_set or "position" in data.model_fields_set
    if move_requested:
        source_column = card.column
        target_column = data.column or card.column
        target_position = data.position

        if target_column == source_column:
            siblings = await _cards_for_column(db, card.group_id, source_column, exclude_card_id=card.id)
            insert_at = card.position if target_position is None else min(target_position, len(siblings))
            siblings.insert(insert_at, card)
            card.column = target_column
            _normalize_positions(siblings)
        else:
            source_siblings = await _cards_for_column(
                db,
                card.group_id,
                source_column,
                exclude_card_id=card.id,
            )
            _normalize_positions(source_siblings)

            target_siblings = await _cards_for_column(db, card.group_id, target_column, exclude_card_id=card.id)
            insert_at = len(target_siblings) if target_position is None else min(target_position, len(target_siblings))
            card.column = target_column
            target_siblings.insert(insert_at, card)
            _normalize_positions(target_siblings)

    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: int, db: AsyncSession = Depends(get_db)) -> None:
    card = await _get_card_or_404(db, card_id)
    group_id = card.group_id
    column = card.column

    await db.delete(card)
    await db.flush()

    remaining = await _cards_for_column(db, group_id, column)
    _normalize_positions(remaining)

    await db.commit()