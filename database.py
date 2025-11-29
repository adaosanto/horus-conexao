from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from contextlib import asynccontextmanager # Use asynccontextmanager
from settings import settings # Assuming settings.DATABASE_URL is an async URL

# 1. Use the asynchronous engine creator
engine = create_async_engine(settings.DATABASE_URL, echo=False) 

Base = declarative_base()

__all__ = ["TagModel"]

class TagModel(Base):
    '''Model para armazenar as movimentações das tags BLE'''
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String, index=True, nullable=False)
    rssi = Column(Integer, nullable=False)
    gateway = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Índice composto para melhorar queries de stats e history
    __table_args__ = (
        Index('idx_mac_timestamp', 'mac', 'timestamp'),
    )

    def __repr__(self):
        # A good practice is to avoid heavy operations (like DB access) in __repr__, 
        # but this simple formatting is fine.
        return f"<TagModel(mac={self.mac}, rssi={self.rssi}, gateway={self.gateway}, timestamp={self.timestamp})>"

# 2. Use AsyncSession with the async engine
# Note: You can use @asynccontextmanager instead of defining a function with `yield` for dependency injection
@asynccontextmanager
async def get_session_context():
    """Provides an async session context manager."""
    async with AsyncSession(
        engine, expire_on_commit=False
    ) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Dependency para FastAPI
async def get_session_dependency():
    """Dependency para FastAPI que gerencia commit/rollback automaticamente."""
    async with AsyncSession(
        engine, expire_on_commit=False
    ) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
