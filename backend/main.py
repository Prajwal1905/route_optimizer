from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import OptimizeRequest, OptimizeResponse, Order, Vehicle, Location
from solver import solve_vrp
from conflicts import detect_conflicts
from database import Base, engine, get_db
from db_models import VehicleDB, OrderDB, RouteRunDB, RouteStopDB

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Intelligent Route Optimization System")

active_connections: list[WebSocket] = []


async def broadcast_routes(resp: OptimizeResponse):
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(resp.model_dump())
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections.remove(ws)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/vehicles")
def create_vehicle(vehicle: Vehicle, db: Session = Depends(get_db)):
    db_vehicle = VehicleDB(
        id=vehicle.id,
        start_lat=vehicle.start_location.lat,
        start_lng=vehicle.start_location.lng,
        capacity=vehicle.capacity,
        max_route_minutes=vehicle.max_route_minutes,
    )
    db.merge(db_vehicle)
    db.commit()
    return {"status": "saved", "id": vehicle.id}


@app.get("/vehicles")
def list_vehicles(db: Session = Depends(get_db)):
    rows = db.query(VehicleDB).all()
    return [
        Vehicle(
            id=r.id,
            start_location=Location(lat=r.start_lat, lng=r.start_lng),
            capacity=r.capacity,
            max_route_minutes=r.max_route_minutes,
        )
        for r in rows
    ]


@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    db.query(VehicleDB).filter(VehicleDB.id == vehicle_id).delete()
    db.commit()
    return {"status": "deleted"}

@app.post("/orders")
def create_order(order: Order, db: Session = Depends(get_db)):
    db_order = OrderDB(
        id=order.id,
        lat=order.location.lat,
        lng=order.location.lng,
        priority=order.priority,
        demand=order.demand,
        time_window_start=order.time_window_start,
        time_window_end=order.time_window_end,
    )
    db.merge(db_order)
    db.commit()
    return {"status": "saved", "id": order.id}


@app.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    rows = db.query(OrderDB).filter(OrderDB.status == "pending").all()
    return [
        Order(
            id=r.id,
            location=Location(lat=r.lat, lng=r.lng),
            priority=r.priority,
            demand=r.demand,
            time_window_start=r.time_window_start,
            time_window_end=r.time_window_end,
        )
        for r in rows
    ]


@app.delete("/orders/{order_id}")
def delete_order(order_id: str, db: Session = Depends(get_db)):
    db.query(OrderDB).filter(OrderDB.id == order_id).delete()
    db.commit()
    return {"status": "deleted"}


def _save_run(req: OptimizeRequest, resp: OptimizeResponse, db: Session):
    run = RouteRunDB(
        total_vehicles=len(req.vehicles),
        total_orders=len(req.orders),
        unassigned_count=len(resp.unassigned_orders),
        conflict_count=len(resp.conflicts),
    )
    db.add(run)
    db.flush()

    for route in resp.routes:
        for stop in route.stops:
            db.add(
                RouteStopDB(
                    run_id=run.id,
                    vehicle_id=route.vehicle_id,
                    order_id=stop.order_id,
                    sequence=stop.sequence,
                    eta_minutes=stop.eta_minutes,
                )
            )
    db.commit()


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest, db: Session = Depends(get_db)):
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    _save_run(req, resp, db)
    return resp


@app.post("/reroute", response_model=OptimizeResponse)
async def reroute(req: OptimizeRequest, db: Session = Depends(get_db)):
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    _save_run(req, resp, db)
    await broadcast_routes(resp)
    return resp


@app.websocket("/ws/routes")
async def routes_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)