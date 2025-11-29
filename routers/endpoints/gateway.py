from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import GatewayModel, get_session_dependency
from schemas import Gateway, GatewayUpdate

router = APIRouter()


def keep_alnum(s: str) -> str:
    """Remove tudo que não for letra ou número."""
    return "".join(ch for ch in s if ch.isalnum())


# Util 
async def get_gateway(mac: str, db: AsyncSession) -> GatewayModel:
    """Busca um gateway pelo MAC"""
    mac = keep_alnum(mac.lower())
    result = await db.execute(select(GatewayModel).where(GatewayModel.mac == mac))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")
    return gateway


@router.post("/")
async def create_gateway(
    gateway: Gateway, db: AsyncSession = Depends(get_session_dependency)
):
    mac = keep_alnum(gateway.mac.lower())

    result = await db.execute(
        select(GatewayModel).where(
            or_(GatewayModel.mac == mac, GatewayModel.name == gateway.name)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Gateway already exists")

    new_gateway = GatewayModel(
        mac=mac, name=gateway.name, geolocation=gateway.geolocation.__dict__
    )
    db.add(new_gateway)
    await db.flush()  # Flush para garantir que o ID seja gerado
    await db.refresh(new_gateway)  # Refresh para garantir que temos todos os dados
    return new_gateway


@router.put("/{mac}")
async def update_gateway(
    mac: str, gateway: GatewayUpdate, db: AsyncSession = Depends(get_session_dependency)
):
    mac = keep_alnum(mac.lower())
    existing_gateway = await get_gateway(mac, db)
    
    # Atualiza apenas os campos fornecidos
    if gateway.name is not None and existing_gateway.name != gateway.name:
        existing_gateway.name = gateway.name
    
    if gateway.geolocation is not None:
        geolocation_dict = gateway.geolocation.__dict__ if hasattr(gateway.geolocation, '__dict__') else gateway.geolocation
        if existing_gateway.geolocation != geolocation_dict:
            existing_gateway.geolocation = geolocation_dict
    
    # Flush para garantir que as mudanças sejam aplicadas antes do commit automático
    await db.flush()
    
    return existing_gateway

@router.get("/")
async def get_gateways(db: AsyncSession = Depends(get_session_dependency)):
    gateways = await db.execute(select(GatewayModel))
    return gateways.scalars().all()

@router.post("/{mac}/tags")
async def add_tag(mac: str, tag: str, db: AsyncSession = Depends(get_session_dependency)):
    mac = keep_alnum(mac.lower())
    existing_gateway = await get_gateway(mac, db)
    # TODO: Implementar lógica de adicionar tag
    ...