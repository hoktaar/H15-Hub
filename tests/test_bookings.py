import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from h15hub.database import Base, get_db
from h15hub.models.booking import Booking, BookingStatus


# Minimale App-Instanz für Booking-Tests (ohne Device Registry)
@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def make_booking(device_id="lasercutter", member="Alice", offset_hours=0, duration_hours=2):
    now = datetime(2026, 3, 10, 10, 0) + timedelta(hours=offset_hours)
    return Booking(
        device_id=device_id,
        member_name=member,
        start_time=now,
        end_time=now + timedelta(hours=duration_hours),
        status=BookingStatus.CONFIRMED,
    )


@pytest.mark.asyncio
async def test_create_booking(db_session):
    booking = make_booking()
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)
    assert booking.id is not None
    assert booking.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_cancel_booking(db_session):
    booking = make_booking()
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)

    booking.status = BookingStatus.CANCELLED
    await db_session.commit()
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED


@pytest.mark.asyncio
async def test_multiple_bookings_no_overlap(db_session):
    """Zwei Buchungen auf verschiedenen Geräten = kein Konflikt."""
    b1 = make_booking(device_id="lasercutter", member="Alice")
    b2 = make_booking(device_id="bambu-p1s-1", member="Bob")
    db_session.add_all([b1, b2])
    await db_session.commit()
    # Beide sollten erfolgreich gespeichert sein
    assert b1.id != b2.id
