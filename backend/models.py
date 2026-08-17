from pydantic import BaseModel
from typing import Optional


class Location(BaseModel):
    lat: float
    lng: float


class Order(BaseModel):
    id: str
    location: Location
    priority: int = 1          
    demand: int = 1            
    time_window_start: Optional[int] = None   
    time_window_end: Optional[int] = None


class Vehicle(BaseModel):
    id: str
    start_location: Location
    capacity: int = 10
    max_route_minutes: int = 480  


class OptimizeRequest(BaseModel):
    orders: list[Order]
    vehicles: list[Vehicle]


class RouteStop(BaseModel):
    order_id: str
    eta_minutes: int
    sequence: int


class VehicleRoute(BaseModel):
    vehicle_id: str
    stops: list[RouteStop]
    total_distance_km: float
    total_time_minutes: int


class OptimizeResponse(BaseModel):
    routes: list[VehicleRoute]
    unassigned_orders: list[str]
    conflicts: list[str] = []