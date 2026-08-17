from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import OptimizeRequest, OptimizeResponse, Order, Vehicle, Location
from solver import solve_vrp
from conflicts import detect_conflicts
from database import Base, engine, get_db
from db_models import VehicleDB, OrderDB, RouteRunDB, RouteStopDB

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Intelligent Route Optimization System")

active_connections: list[WebSocket] = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def broadcast_routes(resp: OptimizeResponse):
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(resp.model_dump())
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections.remove(ws)


def save_run(db: Session, req: OptimizeRequest, resp: OptimizeResponse) -> int:
    run = RouteRunDB(
        total_vehicles=len(req.vehicles),
        total_orders=len(req.orders),
        unassigned_count=len(resp.unassigned_orders),
        conflict_count=len(resp.conflicts),
    )
    db.add(run)
    db.flush()  # get run.id before commit

    for route in resp.routes:
        for stop in route.stops:
            db.add(RouteStopDB(
                run_id=run.id,
                vehicle_id=route.vehicle_id,
                order_id=stop.order_id,
                sequence=stop.sequence,
                eta_minutes=stop.eta_minutes,
            ))

    db.commit()
    return run.id


@app.get("/")
def health():
    return {"status": "ok"}


# ---------------- Vehicles CRUD ----------------

def vehicle_to_dict(v: VehicleDB) -> dict:
    return {
        "id": v.id,
        "start_location": {"lat": v.start_lat, "lng": v.start_lng},
        "capacity": v.capacity,
        "max_route_minutes": v.max_route_minutes,
    }


def order_to_dict(o: OrderDB) -> dict:
    return {
        "id": o.id,
        "location": {"lat": o.lat, "lng": o.lng},
        "priority": o.priority,
        "demand": o.demand,
        "time_window_start": o.time_window_start,
        "time_window_end": o.time_window_end,
        "status": o.status,
    }


@app.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    return [vehicle_to_dict(v) for v in db.query(VehicleDB).all()]


@app.post("/vehicles")
def create_vehicle(vehicle: Vehicle, db: Session = Depends(get_db)):
    existing = db.query(VehicleDB).filter(VehicleDB.id == vehicle.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle with this id already exists")
    db_vehicle = VehicleDB(
        id=vehicle.id,
        start_lat=vehicle.start_location.lat,
        start_lng=vehicle.start_location.lng,
        capacity=vehicle.capacity,
        max_route_minutes=vehicle.max_route_minutes,
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return vehicle_to_dict(db_vehicle)


@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    db_vehicle = db.query(VehicleDB).filter(VehicleDB.id == vehicle_id).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(db_vehicle)
    db.commit()
    return {"deleted": vehicle_id}


# ---------------- Orders CRUD ----------------

@app.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    return [order_to_dict(o) for o in db.query(OrderDB).all()]


@app.post("/orders")
def create_order(order: Order, db: Session = Depends(get_db)):
    existing = db.query(OrderDB).filter(OrderDB.id == order.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order with this id already exists")
    db_order = OrderDB(
        id=order.id,
        lat=order.location.lat,
        lng=order.location.lng,
        priority=order.priority,
        demand=order.demand,
        time_window_start=order.time_window_start,
        time_window_end=order.time_window_end,
        status="pending",
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return order_to_dict(db_order)


@app.delete("/orders/{order_id}")
def delete_order(order_id: str, db: Session = Depends(get_db)):
    db_order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(db_order)
    db.commit()
    return {"deleted": order_id}


@app.patch("/orders/{order_id}/status")
def update_order_status(order_id: str, status: str, db: Session = Depends(get_db)):
    db_order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    db_order.status = status
    db.commit()
    db.refresh(db_order)
    return order_to_dict(db_order)


# ---------------- Optimization ----------------

@app.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest, db: Session = Depends(get_db)):
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    save_run(db, req, resp)
    return resp


@app.post("/reroute", response_model=OptimizeResponse)
async def reroute(req: OptimizeRequest, db: Session = Depends(get_db)):
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    save_run(db, req, resp)
    await broadcast_routes(resp)
    return resp


# ---------------- Route History ----------------

@app.get("/route-history")
def route_history(limit: int = 20, db: Session = Depends(get_db)):
    runs = (
        db.query(RouteRunDB)
        .order_by(desc(RouteRunDB.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": run.id,
            "created_at": run.created_at,
            "total_vehicles": run.total_vehicles,
            "total_orders": run.total_orders,
            "unassigned_count": run.unassigned_count,
            "conflict_count": run.conflict_count,
        }
        for run in runs
    ]


@app.get("/route-history/{run_id}")
def route_history_detail(run_id: int, db: Session = Depends(get_db)):
    run = db.query(RouteRunDB).filter(RouteRunDB.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    stops = (
        db.query(RouteStopDB)
        .filter(RouteStopDB.run_id == run_id)
        .order_by(RouteStopDB.vehicle_id, RouteStopDB.sequence)
        .all()
    )

    routes_by_vehicle: dict[str, list[dict]] = {}
    for stop in stops:
        routes_by_vehicle.setdefault(stop.vehicle_id, []).append({
            "order_id": stop.order_id,
            "sequence": stop.sequence,
            "eta_minutes": stop.eta_minutes,
        })

    return {
        "id": run.id,
        "created_at": run.created_at,
        "total_vehicles": run.total_vehicles,
        "total_orders": run.total_orders,
        "unassigned_count": run.unassigned_count,
        "conflict_count": run.conflict_count,
        "routes": [
            {"vehicle_id": vid, "stops": stops}
            for vid, stops in routes_by_vehicle.items()
        ],
    }


# ---------------- WebSocket ----------------

@app.websocket("/ws/routes")
async def routes_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive, ignore client pings
    except WebSocketDisconnect:
        active_connections.remove(websocket)