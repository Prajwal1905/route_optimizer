# Intelligent Route Optimization System

A live delivery-fleet dispatch tool. Give it orders and vehicles, and it computes
the optimal assignment and sequence of stops per vehicle — minimizing delivery
time and operational cost, respecting vehicle capacity, and prioritizing urgent
orders. When a new order arrives mid-day, it re-optimizes in real time and pushes
the update to every connected client over WebSocket.

## Problem

Delivery companies running multiple vehicles across multiple destinations need to
decide, continuously: which vehicle takes which order, in what sequence, without
exceeding capacity or shift time, while still honoring priority and minimizing
cost. Doing this by hand or with a simple "nearest stop next" script leaves real
efficiency on the table.

## What this does differently

This isn't a shortest-path script — it's a real constraint-based optimizer:

- **Google OR-Tools** solves a full Capacitated Vehicle Routing Problem with Time
  Windows (CVRPTW): capacity constraints, per-order time windows, and soft
  priority weighting (higher-priority orders are far more costly to leave
  unassigned).
- **Real road data**, not straight-line distance — **OSRM** computes true
  driving distance, duration, and turn-by-turn route geometry between every
  pair of locations, with a haversine fallback if OSRM is unreachable.
- **Fleet load balancing** — a span-cost penalty discourages piling every order
  onto one vehicle while others sit idle, matching how a real dispatcher would
  want a fleet used.
- **Conflict detection** — flags double-booked orders, overloaded vehicles,
  shift-time overruns, and unassigned high-priority orders.
- **Quantified efficiency** — every optimization run is compared against a
  naive nearest-neighbor baseline (the "obvious" way to route by hand), and the
  UI shows the exact % saved on distance, time, and cost.
- **Live re-optimization** — a new order arriving mid-shift triggers a full
  re-solve, broadcast instantly to every connected client over WebSocket.
- **Persistent history** — every run (routes, stops, conflicts) is saved to
  PostgreSQL, not just held in memory.

## Architecture

```
┌─────────────┐      REST + WebSocket      ┌──────────────┐
│   React      │ ─────────────────────────▶ │   FastAPI     │
│  (Leaflet     │ ◀───────────────────────── │   backend      │
│   map UI)    │                             └──────┬───────┘
└─────────────┘                                     │
                                          ┌──────────┼───────────┐
                                          ▼          ▼           ▼
                                     OR-Tools      OSRM        PostgreSQL
                                     (solver)   (real roads)  (persistence)
```

**Backend** — Python, FastAPI
| File | Responsibility |
|---|---|
| `main.py` | REST API (orders, vehicles, optimize, reroute, route history), WebSocket broadcast |
| `solver.py` | OR-Tools CVRPTW solver, cost model, naive-baseline comparison |
| `distance.py` | OSRM distance/duration matrices + route geometry, haversine fallback |
| `conflicts.py` | Post-solve conflict detection |
| `models.py` | Pydantic request/response schemas |
| `database.py` / `db_models.py` | SQLAlchemy connection + ORM tables |

**Frontend** — React + Vite
| File | Responsibility |
|---|---|
| `App.jsx` | State, API calls, dispatch console UI |
| `MapView.jsx` | Leaflet map — vehicles, orders, real road-following route polylines |

## Running locally

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
# create a .env with DATABASE_URL=postgresql://user:pass@localhost/route_optimizer
uvicorn main:app --reload
```
Runs at `http://localhost:8000` — interactive API docs at `/docs`.

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`.

> OSRM uses the public `router.project-osrm.org` demo server — no separate
> setup needed, but it's rate-limited and best-effort; distance/time falls
> back to a haversine estimate if it's unreachable.

## API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/orders` | List all orders |
| POST | `/orders` | Create an order |
| DELETE | `/orders/{id}` | Delete an order |
| PATCH | `/orders/{id}/status` | Update order status (e.g. mark delivered) |
| GET | `/vehicles` | List all vehicles |
| POST | `/vehicles` | Create a vehicle |
| DELETE | `/vehicles/{id}` | Delete a vehicle |
| POST | `/optimize` | Run the solver on the given orders/vehicles |
| POST | `/reroute` | Re-solve and broadcast the update over WebSocket |
| GET | `/route-history` | List past optimization runs |
| GET | `/route-history/{run_id}` | Full stop-by-stop detail for one run |
| WS | `/ws/routes` | Live route updates |

## Tech stack

FastAPI · Google OR-Tools · OSRM · PostgreSQL (SQLAlchemy) · React · Vite ·
Leaflet · WebSocket

## Team

Team 02 — Prajwal Ramrao Khade, P. Jaswant Rao, Jensa Rachel, Parth Bhaskar Masurkar

## Roadmap / future work

- Mark orders delivered and clean up completed routes automatically
- Live animated vehicle movement along the route on the map
- Authentication and multi-tenant fleets
- Multi-day scheduling
- Hosted deployment with a public demo link