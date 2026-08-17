from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class VehicleDB(Base):
    __tablename__ = "vehicles"

    id = Column(String, primary_key=True)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)
    capacity = Column(Integer, default=10)
    max_route_minutes = Column(Integer, default=480)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    priority = Column(Integer, default=1)
    demand = Column(Integer, default=1)
    time_window_start = Column(Integer, nullable=True)
    time_window_end = Column(Integer, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class RouteRunDB(Base):
    __tablename__ = "route_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_vehicles = Column(Integer)
    total_orders = Column(Integer)
    unassigned_count = Column(Integer)
    conflict_count = Column(Integer)

    stops = relationship("RouteStopDB", back_populates="run", cascade="all, delete-orphan")


class RouteStopDB(Base):
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("route_runs.id"))
    vehicle_id = Column(String)
    order_id = Column(String)
    sequence = Column(Integer)
    eta_minutes = Column(Integer)

    run = relationship("RouteRunDB", back_populates="stops")