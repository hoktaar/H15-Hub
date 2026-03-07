from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.database import get_db
from h15hub.models.booking import Booking, BookingStatus

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingCreate(BaseModel):
    device_id: str
    member_name: str
    start_time: datetime
    end_time: datetime
    note: str | None = None


class BookingResponse(BaseModel):
    id: int
    device_id: str
    member_name: str
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    note: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[BookingResponse])
async def list_bookings(
    device_id: str | None = None,
    date: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Booking]:
    stmt = select(Booking).where(Booking.status != BookingStatus.CANCELLED)
    if device_id:
        stmt = stmt.where(Booking.device_id == device_id)
    if date:
        day = datetime.fromisoformat(date).date()
        stmt = stmt.where(
            and_(
                Booking.start_time >= datetime.combine(day, datetime.min.time()),
                Booking.start_time < datetime.combine(day, datetime.max.time()),
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking(
    data: BookingCreate,
    db: AsyncSession = Depends(get_db),
) -> Booking:
    if data.start_time >= data.end_time:
        raise HTTPException(status_code=400, detail="start_time muss vor end_time liegen")

    # Überschneidungs-Check
    conflict = await db.execute(
        select(Booking).where(
            and_(
                Booking.device_id == data.device_id,
                Booking.status != BookingStatus.CANCELLED,
                Booking.start_time < data.end_time,
                Booking.end_time > data.start_time,
            )
        )
    )
    if conflict.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="Zeitkonflikt: Gerät ist in diesem Zeitraum bereits gebucht",
        )

    booking = Booking(
        device_id=data.device_id,
        member_name=data.member_name,
        start_time=data.start_time,
        end_time=data.end_time,
        status=BookingStatus.CONFIRMED,
        note=data.note,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


@router.delete("/{booking_id}", status_code=204)
async def cancel_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
    booking.status = BookingStatus.CANCELLED
    await db.commit()
