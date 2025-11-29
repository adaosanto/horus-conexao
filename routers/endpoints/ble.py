"""API FastAPI para gerenciamento de tags BLE/MQTT"""

import hashlib
import math
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import GatewayModel, TagModel, get_session_dependency
from models import (IngestRequest, TagHistoryEntry, TagHistoryResponse,
                    TagStatsResponse)


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


def calculate_tag_position(
    gateway_lat: float, gateway_lon: float, tag_mac: str, tag_index: int
) -> Tuple[float, float]:
    """
    Calcula posição da tag próxima ao gateway (1-3 metros de distância).
    Usa hash do MAC para distribuir tags em círculo ao redor do gateway.
    """
    # Gera um número determinístico baseado no MAC
    mac_hash = int(hashlib.md5(tag_mac.encode()).hexdigest(), 16)
    
    # Distância em metros (1 a 3 metros)
    # Usa o hash para determinar a distância de forma determinística
    distance_meters = 1.0 + (mac_hash % 200) / 100.0  # 1.0 a 3.0 metros
    
    # Ângulo em radianos (distribui em círculo completo)
    # Usa tag_index para evitar sobreposição de tags do mesmo gateway
    angle_rad = (mac_hash % 360) * (math.pi / 180.0) + (tag_index * 0.5)
    
    # Raio da Terra em metros
    earth_radius = 6371000
    
    # Converte distância em metros para graus
    # 1 grau de latitude ≈ 111 km
    # 1 grau de longitude ≈ 111 km * cos(latitude)
    lat_offset = (distance_meters / 111000) * math.cos(angle_rad)
    lon_offset = (distance_meters / (111000 * math.cos(math.radians(gateway_lat)))) * math.sin(angle_rad)
    
    tag_lat = gateway_lat + lat_offset
    tag_lon = gateway_lon + lon_offset
    
    return tag_lat, tag_lon


router = APIRouter()


@router.post("/ingest")
async def ingest(
    payload: IngestRequest, db: AsyncSession = Depends(get_session_dependency)
):
    """
    Recebe pacotes do gateway BLE/MQTT e atualiza dados das tags.
    Também salva histórico de cada leitura.
    """
    gateway = payload.gw or "unknown"
    all_tags = []
    for item in payload.adv:
        mac = item.get("mac")
        rssi = item.get("rssi")
        battery_level = item.get("battery")
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

        # Salva dados atuais (gateway_mac pode ser None se o gateway não existir)
        all_tags.append(TagModel(mac=mac, rssi=rssi, gateway_mac=gateway, timestamp=dt, battery_level=battery_level))

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

    # Busca a última entrada de cada MAC com join no gateway
    subquery = (
        select(TagModel.mac, func.max(TagModel.timestamp).label("max_timestamp"))
        .group_by(TagModel.mac)
        .subquery()
    )

    query = (
        select(TagModel, GatewayModel)
        .outerjoin(
            GatewayModel, TagModel.gateway_mac == GatewayModel.mac
        )
        .join(
            subquery,
            (TagModel.mac == subquery.c.mac)
            & (TagModel.timestamp == subquery.c.max_timestamp),
        )
    )

    result = await db.execute(query)
    rows = result.all()

    # Agrupa tags por gateway para calcular índices
    gateway_tag_counts = {}
    stats = []
    
    for row in rows:
        tag, gateway = row
        presence = "present" if tag.timestamp >= threshold else "absent"
        
        # Calcula coordenadas se o gateway tiver geolocation
        tag_lat = None
        tag_lon = None
        
        if gateway and gateway.geolocation:
            geoloc = gateway.geolocation
            if isinstance(geoloc, dict):
                gateway_lat = geoloc.get("latitude")
                gateway_lon = geoloc.get("longitude")
                
                if gateway_lat is not None and gateway_lon is not None:
                    # Conta quantas tags já foram processadas para este gateway
                    gateway_key = tag.gateway_mac or "unknown"
                    if gateway_key not in gateway_tag_counts:
                        gateway_tag_counts[gateway_key] = 0
                    tag_index = gateway_tag_counts[gateway_key]
                    gateway_tag_counts[gateway_key] += 1
                    
                    # Calcula posição da tag próxima ao gateway
                    tag_lat, tag_lon = calculate_tag_position(
                        gateway_lat, gateway_lon, tag.mac, tag_index
                    )
        
        stats.append(
            TagStatsResponse(
                mac=tag.mac,
                last_rssi=tag.rssi,
                gateway=tag.gateway_mac or "unknown",
                last_seen=int(tag.timestamp.timestamp()),
                last_seen_humanized=humanize_datetime(tag.timestamp),
                presence=presence,
                latitude=tag_lat,
                longitude=tag_lon,
            )
        )

    return stats


@router.get("/stats/{mac}", response_model=TagStatsResponse)
async def get_stats(mac: str, db: AsyncSession = Depends(get_session_dependency)):
    """Retorna dados mais recentes de uma tag específica"""
    mac = mac.lower()

    # Busca a última entrada deste MAC com join no gateway
    query = (
        select(TagModel, GatewayModel)
        .outerjoin(GatewayModel, TagModel.gateway_mac == GatewayModel.mac)
        .where(TagModel.mac == mac)
        .order_by(desc(TagModel.timestamp))
        .limit(1)
    )

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="MAC não encontrado")

    tag, gateway = row

    now = datetime.now()
    threshold = now - timedelta(seconds=10)
    presence = "present" if tag.timestamp >= threshold else "absent"

    # Calcula coordenadas se o gateway tiver geolocation
    tag_lat = None
    tag_lon = None

    if gateway and gateway.geolocation:
        geoloc = gateway.geolocation
        if isinstance(geoloc, dict):
            gateway_lat = geoloc.get("latitude")
            gateway_lon = geoloc.get("longitude")

            if gateway_lat is not None and gateway_lon is not None:
                # Para uma única tag, usa índice 0
                tag_lat, tag_lon = calculate_tag_position(
                    gateway_lat, gateway_lon, tag.mac, 0
                )

    return TagStatsResponse(
        mac=tag.mac,
        last_rssi=tag.rssi,
        gateway=tag.gateway_mac or "unknown",
        last_seen=int(tag.timestamp.timestamp()),
        last_seen_humanized=humanize_datetime(tag.timestamp),
        presence=presence,
        latitude=tag_lat,
        longitude=tag_lon,
    )


@router.get("/history/{mac}", response_model=TagHistoryResponse)
async def get_history(
    mac: str,
    limit: int = Query(
        default=100, ge=1, le=1000, description="Número máximo de entradas"
    ),
    start_time: int = Query(default=None, description="Timestamp inicial (opcional)"),
    end_time: int = Query(default=None, description="Timestamp final (opcional)"),
    db: AsyncSession = Depends(get_session_dependency),
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
        select(TagModel).where(TagModel.mac == mac).order_by(desc(TagModel.timestamp))
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
            timestamp=int(tag.timestamp.timestamp()), rssi=tag.rssi, gateway=tag.gateway_mac or "unknown"
        )
        for tag in tags
    ]

    return TagHistoryResponse(mac=mac, entries=entries, total=len(entries))
