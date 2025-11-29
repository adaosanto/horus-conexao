from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class IngestRequest(BaseModel):
    """Payload recebido no endpoint /ingest"""
    gw: Optional[str] = Field(default="unknown", description="Gateway ID")
    adv: List[dict] = Field(default_factory=list, description="Lista de anúncios BLE")


class TagReading(BaseModel):
    """Leitura individual de uma tag"""
    mac: str
    rssi: int
    tm: Optional[int] = None


class TagData(BaseModel):
    """Dados atuais de uma tag"""
    mac: str
    last_rssi: int
    last_seen: int
    gateway: str


class TagStatsResponse(BaseModel):
    """Resposta do endpoint /stats"""
    mac: str
    last_rssi: int
    gateway: str
    last_seen: int
    last_seen_humanized: str = Field(description="Data formatada de forma humanizada")
    presence: str


class TagHistoryEntry(BaseModel):
    """Entrada do histórico de uma tag"""
    timestamp: int
    rssi: int
    gateway: str


class TagHistoryResponse(BaseModel):
    """Resposta do endpoint /history/{mac}"""
    mac: str
    entries: List[TagHistoryEntry]
    total: int
