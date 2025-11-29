from contextlib import asynccontextmanager  # Use asynccontextmanager

from sqlalchemy import ForeignKey, JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from settings import settings  # Assuming settings.DATABASE_URL is an async URL

# 1. Use the asynchronous engine creator
engine = create_async_engine(settings.DATABASE_URL, echo=False)

Base = declarative_base()

__all__ = ["TagModel", "GatewayModel"]


class GatewayModel(Base):
    __tablename__ = "gateways"
    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String, index=True, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)
    geolocation = Column(JSON, nullable=False)
    
    tags = relationship("TagModel", back_populates="gateway")

class TagModel(Base):
    """Model para armazenar as movimentações das tags BLE"""

    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    battery_level = Column(Integer, nullable=True)
    mac = Column(String, index=True, nullable=False)
    rssi = Column(Integer, nullable=False)
    gateway_mac = Column(String, ForeignKey("gateways.mac", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Índice composto para melhorar queries de stats e history
    __table_args__ = (Index("idx_mac_timestamp", "mac", "timestamp"),)

    gateway = relationship("GatewayModel", back_populates="tags", foreign_keys=[gateway_mac])

    def __repr__(self):
        # A good practice is to avoid heavy operations (like DB access) in __repr__,
        # but this simple formatting is fine.
        return f"<TagModel(mac={self.mac}, rssi={self.rssi}, gateway={self.gateway}, timestamp={self.timestamp})>"


# 2. Use AsyncSession with the async engine
# Note: You can use @asynccontextmanager instead of defining a function with `yield` for dependency injection
@asynccontextmanager
async def get_session_context():
    """Provides an async session context manager."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Dependency para FastAPI
async def get_session_dependency():
    """Dependency para FastAPI que gerencia commit/rollback automaticamente."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
