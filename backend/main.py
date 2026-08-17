from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import OptimizeRequest, OptimizeResponse
from solver import solve_vrp
from conflicts import detect_conflicts

app = FastAPI(title="Intelligent Route Optimization System")

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