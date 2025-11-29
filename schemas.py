from pydantic import BaseModel
from pydantic_extra_types.coordinate import Latitude, Longitude
from typing import Optional


class Geolocation(BaseModel):
    latitude: Latitude
    longitude: Longitude

    def __dict__(self):
        return {"type": "Point", "coordinates": [self.longitude, self.latitude]}


class TagStatsResponse(BaseModel): ...


class Gateway(BaseModel):
    name: str
    mac: str
    geolocation: Geolocation

class GatewayUpdate(BaseModel):
    name: Optional[str] = None
    geolocation: Optional[Geolocation] = None