from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models import OptimizeRequest, OptimizeResponse
from solver import solve_vrp
from conflicts import detect_conflicts

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


@app.post("/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest):
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    return resp


@app.post("/reroute", response_model=OptimizeResponse)
async def reroute(req: OptimizeRequest):
    
    resp = solve_vrp(req)
    resp.conflicts = detect_conflicts(req, resp)
    await broadcast_routes(resp)
    return resp


@app.websocket("/ws/routes")
async def routes_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive, ignore client pings
    except WebSocketDisconnect:
        active_connections.remove(websocket)