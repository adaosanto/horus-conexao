"""API FastAPI para gerenciamento de tags BLE/MQTT"""
import time
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from models import (
    IngestRequest,
    TagStatsResponse,
    TagHistoryResponse,
    TagHistoryEntry
)
from database import get_session_dependency, TagModel


def humanize_datetime(dt: datetime) -> str:
    """Formata datetime de forma humanizada"""
    now = datetime.now()
    diff = now - dt
    
    if diff.total_seconds() < 60:
        seconds = int(diff.total_seconds())
        return f"há {seconds} segundo{'s' if seconds != 1 else ''}"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"há {hours} hora{'s' if hours != 1 else ''}"
    elif diff.days < 7:
        days = diff.days
        return f"há {days} dia{'s' if days != 1 else ''}"
    else:
        return dt.strftime("%d/%m/%Y %H:%M:%S")


router = APIRouter()


@router.post("/ingest")
async def ingest(payload: IngestRequest, db: AsyncSession = Depends(get_session_dependency)):
    """
    Recebe pacotes do gateway BLE/MQTT e atualiza dados das tags.
    Também salva histórico de cada leitura.
    """
    gateway = payload.gw or "unknown"
    all_tags = []
    for item in payload.adv:
        mac = item.get("mac")
        rssi = item.get("rssi")
        timestamp = item.get("tm")
        if not mac or rssi is None:
            continue
        
        mac = mac.lower()
        
        try:
            rssi = int(rssi)
        except (ValueError, TypeError):
            continue
        
        try:
            ts = int(timestamp) if timestamp else int(time.time())
            # Converte timestamp para datetime
            dt = datetime.fromtimestamp(ts)
        except (ValueError, TypeError):
            dt = datetime.now()
        
        # Salva dados atuais
        all_tags.append(
            TagModel(
                mac=mac, 
                rssi=rssi, 
                gateway=gateway, 
                timestamp=dt
            )
        )
    
    if all_tags:
        db.add_all(all_tags)
        await db.flush()  # Flush para garantir que os IDs sejam gerados se necessário
        # Commit é feito automaticamente pela dependência
    
    return {"status": "ok", "inserted": len(all_tags)}


@router.get("/stats", response_model=List[TagStatsResponse])
async def list_all_stats(db: AsyncSession = Depends(get_session_dependency)):
    """Lista todas as tags com seus dados mais recentes"""
    now = datetime.now()
    threshold = now - timedelta(seconds=10)
    
    # Busca a última entrada de cada MAC
    subquery = (
        select(
            TagModel.mac,
            func.max(TagModel.timestamp).label("max_timestamp")
        )
        .group_by(TagModel.mac)
        .subquery()
    )
    
    query = (
        select(TagModel)
        .join(
            subquery,
            (TagModel.mac == subquery.c.mac) & 
            (TagModel.timestamp == subquery.c.max_timestamp)
        )
    )
    
    result = await db.execute(query)
    tags = result.scalars().all()
    
    stats = []
    for tag in tags:
        presence = "present" if tag.timestamp >= threshold else "absent"
        stats.append(TagStatsResponse(
            mac=tag.mac,
            last_rssi=tag.rssi,
            gateway=tag.gateway,
            last_seen=int(tag.timestamp.timestamp()),
            last_seen_humanized=humanize_datetime(tag.timestamp),
            presence=presence
        ))
    
    return stats


@router.get("/stats/{mac}", response_model=TagStatsResponse)
async def get_stats(mac: str, db: AsyncSession = Depends(get_session_dependency)):
    """Retorna dados mais recentes de uma tag específica"""
    mac = mac.lower()
    
    # Busca a última entrada deste MAC
    query = (
        select(TagModel)
        .where(TagModel.mac == mac)
        .order_by(desc(TagModel.timestamp))
        .limit(1)
    )
    
    result = await db.execute(query)
    tag = result.scalar_one_or_none()
    
    if not tag:
        raise HTTPException(status_code=404, detail="MAC não encontrado")
    
    now = datetime.now()
    threshold = now - timedelta(seconds=10)
    presence = "present" if tag.timestamp >= threshold else "absent"
    
    return TagStatsResponse(
        mac=tag.mac,
        last_rssi=tag.rssi,
        gateway=tag.gateway,
        last_seen=int(tag.timestamp.timestamp()),
        last_seen_humanized=humanize_datetime(tag.timestamp),
        presence=presence
    )


@router.get("/history/{mac}", response_model=TagHistoryResponse)
async def get_history(
    mac: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Número máximo de entradas"),
    start_time: int = Query(default=None, description="Timestamp inicial (opcional)"),
    end_time: int = Query(default=None, description="Timestamp final (opcional)"),
    db: AsyncSession = Depends(get_session_dependency)
):
    """
    Retorna histórico de leituras de uma tag específica.
    Pode filtrar por intervalo de tempo e limitar quantidade de resultados.
    """
    mac = mac.lower()
    
    # Verifica se a tag existe
    check_query = select(TagModel).where(TagModel.mac == mac).limit(1)
    check_result = await db.execute(check_query)
    if not check_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="MAC não encontrado")
    
    # Constrói query base
    query = (
        select(TagModel)
        .where(TagModel.mac == mac)
        .order_by(desc(TagModel.timestamp))
    )
    
    # Aplica filtros de tempo se fornecidos
    if start_time:
        start_dt = datetime.fromtimestamp(start_time)
        query = query.where(TagModel.timestamp >= start_dt)
    
    if end_time:
        end_dt = datetime.fromtimestamp(end_time)
        query = query.where(TagModel.timestamp <= end_dt)
    
    # Aplica limite
    query = query.limit(limit)
    
    result = await db.execute(query)
    tags = result.scalars().all()
    
    entries = [
        TagHistoryEntry(
            timestamp=int(tag.timestamp.timestamp()),
            rssi=tag.rssi,
            gateway=tag.gateway
        )
        for tag in tags
    ]
    
    return TagHistoryResponse(
        mac=mac,
        entries=entries,
        total=len(entries)
    )

