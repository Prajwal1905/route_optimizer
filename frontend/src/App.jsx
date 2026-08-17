import { useState, useEffect } from "react";
import axios from "axios";
import MapView from "./MapView";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const PRESET_LOCATIONS = [
  { label: "Vashi", lat: 19.0330, lng: 73.0297 },
  { label: "Sanpada", lat: 19.0522, lng: 73.0169 },
  { label: "Nerul", lat: 19.0176, lng: 73.0356 },
  { label: "Kopar Khairane", lat: 19.0728, lng: 73.0055 },
  { label: "Kharghar", lat: 19.0330, lng: 73.0688 },
  { label: "CBD Belapur", lat: 19.0479, lng: 73.0245 },
];

const VEHICLE_COLORS = ["#3cb44b", "#f58231", "#911eb4", "#46f0f0", "#e6194b", "#4363d8"];

export default function App() {
  const [orders, setOrders] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [unassigned, setUnassigned] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [backendUp, setBackendUp] = useState(true);

  const [orderForm, setOrderForm] = useState({ preset: 0, priority: 2, demand: 1 });
  const [vehicleForm, setVehicleForm] = useState({ preset: 0, capacity: 5 });

  const fetchAll = async () => {
    try {
      const [ordersRes, vehiclesRes] = await Promise.all([
        axios.get(`${API_BASE}/orders`),
        axios.get(`${API_BASE}/vehicles`),
      ]);
      setOrders(ordersRes.data);
      setVehicles(vehiclesRes.data);
      setBackendUp(true);
    } catch (err) {
      console.error("Failed to fetch data", err);
      setBackendUp(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const addOrder = async () => {
    const loc = PRESET_LOCATIONS[orderForm.preset];
    const newOrder = {
      id: `o${Date.now()}`,
      location: { lat: loc.lat, lng: loc.lng },
      priority: Number(orderForm.priority),
      demand: Number(orderForm.demand),
    };
    try {
      await axios.post(`${API_BASE}/orders`, newOrder);
      await fetchAll();
    } catch (err) {
      alert("Could not add order — check backend is running");
    }
  };

  const addVehicle = async () => {
    const loc = PRESET_LOCATIONS[vehicleForm.preset];
    const newVehicle = {
      id: `v${Date.now()}`,
      start_location: { lat: loc.lat, lng: loc.lng },
      capacity: Number(vehicleForm.capacity),
    };
    try {
      await axios.post(`${API_BASE}/vehicles`, newVehicle);
      await fetchAll();
    } catch (err) {
      alert("Could not add vehicle — check backend is running");
    }
  };

  const deleteOrder = async (id) => {
    await axios.delete(`${API_BASE}/orders/${id}`);
    await fetchAll();
  };

  const deleteVehicle = async (id) => {
    await axios.delete(`${API_BASE}/vehicles/${id}`);
    await fetchAll();
  };

  const runOptimize = async () => {
    if (orders.length === 0 || vehicles.length === 0) {
      alert("Add at least one order and one vehicle first");
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/optimize`, { orders, vehicles });
      setRoutes(res.data.routes);
      setConflicts(res.data.conflicts);
      setUnassigned(res.data.unassigned_orders);
      setComparison(res.data.comparison || null);
      setBackendUp(true);
    } catch (err) {
      console.error(err);
      alert("Optimize failed — check backend is running");
      setBackendUp(false);
    } finally {
      setLoading(false);
    }
  };

  const simulateNewOrder = async () => {
    const randomPreset = PRESET_LOCATIONS[Math.floor(Math.random() * PRESET_LOCATIONS.length)];
    const newOrder = {
      id: `o${Date.now()}`,
      location: { lat: randomPreset.lat, lng: randomPreset.lng },
      priority: 3,
      demand: 1,
    };
    await axios.post(`${API_BASE}/orders`, newOrder);
    const updatedOrders = [...orders, newOrder];
    setOrders(updatedOrders);

    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/reroute`, { orders: updatedOrders, vehicles });
      setRoutes(res.data.routes);
      setConflicts(res.data.conflicts);
      setUnassigned(res.data.unassigned_orders);
      setComparison(res.data.comparison || null);
    } catch (err) {
      console.error(err);
      alert("Reroute failed — check backend is running");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <span className="eyebrow">Fleet Dispatch · Navi Mumbai</span>
          <h1>Intelligent Route Optimization System</h1>
        </div>
        <div className="status-pill">
          <span
            className="status-dot"
            style={{
              background: backendUp ? "#2DD4BF" : "#FF5A5F",
              boxShadow: `0 0 6px ${backendUp ? "#2DD4BF" : "#FF5A5F"}`,
            }}
          />
          {backendUp ? "Backend connected" : "Backend unreachable"}
        </div>
      </header>

      <div className="panels">
        <div className="panel">
          <p className="panel-title">Add Order</p>
          <div className="field-row">
            <label className="field-label">Location</label>
            <select
              value={orderForm.preset}
              onChange={(e) => setOrderForm({ ...orderForm, preset: Number(e.target.value) })}
            >
              {PRESET_LOCATIONS.map((loc, i) => (
                <option key={i} value={i}>{loc.label}</option>
              ))}
            </select>
          </div>
          <div className="field-inline">
            <div className="field-row">
              <label className="field-label">Priority (1–3)</label>
              <input
                type="number" min="1" max="3"
                value={orderForm.priority}
                onChange={(e) => setOrderForm({ ...orderForm, priority: e.target.value })}
              />
            </div>
            <div className="field-row">
              <label className="field-label">Demand</label>
              <input
                type="number" min="1"
                value={orderForm.demand}
                onChange={(e) => setOrderForm({ ...orderForm, demand: e.target.value })}
              />
            </div>
          </div>
          <button className="btn btn-primary" onClick={addOrder}>Add Order</button>
        </div>

        <div className="panel">
          <p className="panel-title">Add Vehicle</p>
          <div className="field-row">
            <label className="field-label">Depot Location</label>
            <select
              value={vehicleForm.preset}
              onChange={(e) => setVehicleForm({ ...vehicleForm, preset: Number(e.target.value) })}
            >
              {PRESET_LOCATIONS.map((loc, i) => (
                <option key={i} value={i}>{loc.label}</option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <label className="field-label">Capacity</label>
            <input
              type="number" min="1"
              value={vehicleForm.capacity}
              onChange={(e) => setVehicleForm({ ...vehicleForm, capacity: e.target.value })}
            />
          </div>
          <button className="btn btn-primary" onClick={addVehicle}>Add Vehicle</button>
        </div>

        <div className="panel">
          <p className="panel-title">Orders ({orders.length})</p>
          <div className="entity-list">
            {orders.length === 0 && <div className="empty-hint">No orders yet — add one to get started</div>}
            {orders.map((o) => (
              <div key={o.id} className="entity-row">
                <span>
                  <span className="entity-id">{o.id}</span>
                  <span className={`priority-tag priority-${o.priority}`}>P{o.priority}</span>
                </span>
                <button className="icon-btn" onClick={() => deleteOrder(o.id)}>✕</button>
              </div>
            ))}
          </div>

          <p className="panel-title">Vehicles ({vehicles.length})</p>
          <div className="entity-list">
            {vehicles.length === 0 && <div className="empty-hint">No vehicles yet — add one to get started</div>}
            {vehicles.map((v) => (
              <div key={v.id} className="entity-row">
                <span>
                  <span className="entity-id">{v.id}</span>
                  <span className="entity-meta">cap {v.capacity}</span>
                </span>
                <button className="icon-btn" onClick={() => deleteVehicle(v.id)}>✕</button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="action-row">
        <button className="btn btn-run" onClick={runOptimize} disabled={loading}>
          {loading ? "Optimizing…" : "Run Optimization"}
        </button>
        <button className="btn btn-simulate" onClick={simulateNewOrder} disabled={loading || routes.length === 0}>
          Simulate New Order (Dynamic Reroute)
        </button>
      </div>

      {comparison && (
        <div className="comparison-banner">
          <div className="comparison-eyebrow">OR-Tools optimization vs naive nearest-neighbor routing</div>
          <div className="comparison-stats">
            <div>
              <div className="comparison-stat-value">{comparison.distance_saved_pct}%</div>
              <div className="comparison-stat-label">less distance · {comparison.distance_saved_km} km saved</div>
            </div>
            <div>
              <div className="comparison-stat-value">{comparison.time_saved_pct}%</div>
              <div className="comparison-stat-label">less time · {comparison.time_saved_minutes} min saved</div>
            </div>
            <div>
              <div className="comparison-stat-value">{comparison.cost_saved_pct}%</div>
              <div className="comparison-stat-label">lower cost · ₹{comparison.cost_saved} saved</div>
            </div>
          </div>
          <div className="comparison-footer">
            Naive: {comparison.baseline.total_distance_km} km · {comparison.baseline.total_time_minutes} min · ₹{comparison.baseline.total_cost}
            {"   →   "}
            Optimized: {comparison.optimized.total_distance_km} km · {comparison.optimized.total_time_minutes} min · ₹{comparison.optimized.total_cost}
          </div>
        </div>
      )}

      {conflicts.length > 0 && (
        <div className="alert-banner alert-conflict">
          <div className="alert-title">Conflicts detected</div>
          <ul>{conflicts.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}

      {unassigned.length > 0 && (
        <div className="alert-banner alert-unassigned">
          <div className="alert-title">Unassigned orders</div>
          {unassigned.join(", ")}
        </div>
      )}

      <div className="map-wrapper">
        <MapView orders={orders} vehicles={vehicles} routes={routes} />
      </div>

      {routes.length > 0 && (
        <div>
          <p className="route-summary-title">Route Summary</p>
          {routes.map((r, idx) => (
            <div
              key={r.vehicle_id}
              className="route-card"
              style={{ "--vehicle-color": VEHICLE_COLORS[idx % VEHICLE_COLORS.length] }}
            >
              <div className="route-card-head">
                <span className="route-vehicle-id">{r.vehicle_id}</span>
                <span className="route-stats">
                  <span><strong>{r.stops.length}</strong> stops</span>
                  <span><strong>{r.total_distance_km}</strong> km</span>
                  <span><strong>{r.total_time_minutes}</strong> min</span>
                  <span><strong>₹{r.total_cost}</strong></span>
                </span>
              </div>
              <div className="route-path">
                {r.stops.length > 0 ? r.stops.map((s) => s.order_id).join("  →  ") : "No stops assigned"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}