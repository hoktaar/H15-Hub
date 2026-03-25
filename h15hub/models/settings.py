from __future__ import annotations
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from h15hub.database import Base


class DeviceSettings(Base):
    __tablename__ = "device_settings"

    device_id = Column(String, primary_key=True)
    settings_json = Column(String, nullable=False, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
