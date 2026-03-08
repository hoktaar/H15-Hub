from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.auth import require_authenticated_user
from h15hub.database import get_db
from h15hub.models.board import BoardCard, BoardCardColumn, BoardGroup, BoardProject

router = APIRouter(
    prefix="/api/boards",
    tags=["boards"],
    dependencies=[Depends(require_authenticated_user)],
)


class BoardGroupResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class BoardProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    group_id: int


class BoardProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    group_id: int | None = None


class BoardProjectResponse(BaseModel):
    id: int
    name: str
    group_id: int
    group_name: str


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
    project_id: int
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


async def _get_project_or_404(db: AsyncSession, project_id: int) -> BoardProject:
    project = await db.get(BoardProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    return project


async def _get_card_or_404(db: AsyncSession, card_id: int) -> BoardCard:
    card = await db.get(BoardCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Karte nicht gefunden")
    return card


async def _cards_for_column(
    db: AsyncSession,
    project_id: int,
    column: BoardCardColumn,
    *,
    exclude_card_id: int | None = None,
) -> list[BoardCard]:
    stmt = select(BoardCard).where(
        BoardCard.project_id == project_id,
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


async def _ensure_unique_project_name(
    db: AsyncSession,
    name: str,
    *,
    group_id: int,
    exclude_project_id: int | None = None,
) -> None:
    stmt = select(BoardProject).where(
        BoardProject.group_id == group_id,
        func.lower(BoardProject.name) == name.lower(),
    )
    if exclude_project_id is not None:
        stmt = stmt.where(BoardProject.id != exclude_project_id)

    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Projekt existiert in dieser Gruppe bereits")


async def _delete_project_cards(db: AsyncSession, project_id: int) -> None:
    result = await db.execute(
        select(BoardCard).where(
            BoardCard.project_id == project_id,
        )
    )
    for card in result.scalars().all():
        await db.delete(card)


def _clean_project_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise HTTPException(status_code=422, detail="Projektname darf nicht leer sein")
    return value


def _serialize_project(project: BoardProject, group: BoardGroup) -> BoardProjectResponse:
    return BoardProjectResponse(
        id=project.id,
        name=project.name,
        group_id=group.id,
        group_name=group.name,
    )


@router.get("/groups", response_model=list[BoardGroupResponse])
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[BoardGroup]:
    result = await db.execute(select(BoardGroup).order_by(BoardGroup.name))
    return list(result.scalars().all())


@router.get("/projects", response_model=list[BoardProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[BoardProjectResponse]:
    result = await db.execute(
        select(BoardProject, BoardGroup)
        .join(BoardGroup, BoardProject.group_id == BoardGroup.id)
        .order_by(func.lower(BoardGroup.name), func.lower(BoardProject.name), BoardProject.id)
    )
    return [_serialize_project(project, group) for project, group in result.all()]


@router.post(
    "/projects",
    response_model=BoardProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    data: BoardProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> BoardProjectResponse:
    name = _clean_project_name(data.name)

    group = await _get_group_or_404(db, data.group_id)
    await _ensure_unique_project_name(db, name, group_id=group.id)

    project = BoardProject(name=name, group_id=group.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _serialize_project(project, group)


@router.patch("/projects/{project_id}", response_model=BoardProjectResponse)
async def update_project(
    project_id: int,
    data: BoardProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> BoardProjectResponse:
    project = await _get_project_or_404(db, project_id)
    group = await _get_group_or_404(db, project.group_id)

    next_name = project.name
    if "name" in data.model_fields_set and data.name is not None:
        next_name = _clean_project_name(data.name)

    next_group = group
    if "group_id" in data.model_fields_set and data.group_id is not None:
        next_group = await _get_group_or_404(db, data.group_id)

    if next_name != project.name or next_group.id != project.group_id:
        await _ensure_unique_project_name(
            db,
            next_name,
            group_id=next_group.id,
            exclude_project_id=project.id,
        )

    project.name = next_name
    project.group_id = next_group.id

    await db.commit()
    await db.refresh(project)
    return _serialize_project(project, next_group)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)) -> None:
    project = await _get_project_or_404(db, project_id)
    await _delete_project_cards(db, project.id)
    await db.delete(project)
    await db.commit()


@router.get("/projects/{project_id}/cards", response_model=list[BoardCardResponse])
async def list_cards(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[BoardCard]:
    await _get_project_or_404(db, project_id)
    result = await db.execute(
        select(BoardCard)
        .where(BoardCard.project_id == project_id)
        .order_by(BoardCard.position, BoardCard.id)
    )
    return list(result.scalars().all())


@router.post(
    "/projects/{project_id}/cards",
    response_model=BoardCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_card(
    project_id: int,
    data: BoardCardCreate,
    db: AsyncSession = Depends(get_db),
) -> BoardCard:
    await _get_project_or_404(db, project_id)

    siblings = await _cards_for_column(db, project_id, data.column)
    card = BoardCard(
        project_id=project_id,
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
            siblings = await _cards_for_column(db, card.project_id, source_column, exclude_card_id=card.id)
            insert_at = card.position if target_position is None else min(target_position, len(siblings))
            siblings.insert(insert_at, card)
            card.column = target_column
            _normalize_positions(siblings)
        else:
            source_siblings = await _cards_for_column(
                db,
                card.project_id,
                source_column,
                exclude_card_id=card.id,
            )
            _normalize_positions(source_siblings)

            target_siblings = await _cards_for_column(db, card.project_id, target_column, exclude_card_id=card.id)
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
    project_id = card.project_id
    column = card.column

    await db.delete(card)
    await db.flush()

    remaining = await _cards_for_column(db, project_id, column)
    _normalize_positions(remaining)

    await db.commit()