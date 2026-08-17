import { useState } from "react";
import axios from "axios";
import MapView from "./MapView";

const API_BASE = "http://localhost:8000";

const SAMPLE_ORDERS = [
  { id: "o1", location: { lat: 19.076, lng: 72.8777 }, priority: 2, demand: 1 },
  { id: "o2", location: { lat: 19.0896, lng: 72.8656 }, priority: 3, demand: 1 },
  { id: "o3", location: { lat: 19.033, lng: 72.8296 }, priority: 1, demand: 1 },
];

const SAMPLE_VEHICLES = [
  { id: "v1", start_location: { lat: 19.0176, lng: 72.8562 }, capacity: 5 },
  { id: "v2", start_location: { lat: 19.1136, lng: 72.8697 }, capacity: 5 },
];

export default function App() {
  const [orders] = useState(SAMPLE_ORDERS);
  const [vehicles] = useState(SAMPLE_VEHICLES);
  const [routes, setRoutes] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [unassigned, setUnassigned] = useState([]);
  const [loading, setLoading] = useState(false);

  const runOptimize = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/optimize`, { orders, vehicles });
      setRoutes(res.data.routes);
      setConflicts(res.data.conflicts);
      setUnassigned(res.data.unassigned_orders);
    } catch (err) {
      console.error(err);
      alert("Optimize failed - check backend is running");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "sans-serif" }}>
      <h1>Intelligent Route Optimization System</h1>

      <button onClick={runOptimize} disabled={loading} style={{ padding: "10px 20px", marginBottom: "16px" }}>
        {loading ? "Optimizing..." : "Run Optimization"}
      </button>

      {conflicts.length > 0 && (
        <div style={{ background: "#fee", padding: "10px", marginBottom: "10px" }}>
          <strong>Conflicts:</strong>
          <ul>
            {conflicts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {unassigned.length > 0 && (
        <div style={{ background: "#ffe", padding: "10px", marginBottom: "10px" }}>
          <strong>Unassigned orders:</strong> {unassigned.join(", ")}
        </div>
      )}

      <MapView orders={orders} vehicles={vehicles} routes={routes} />

      {routes.length > 0 && (
        <div style={{ marginTop: "20px" }}>
          <h3>Route Summary</h3>
          {routes.map((r) => (
            <div key={r.vehicle_id} style={{ marginBottom: "8px" }}>
              <strong>{r.vehicle_id}</strong> — {r.stops.length} stops,{" "}
              {r.total_distance_km} km, {r.total_time_minutes} min
              <br />
              Order: {r.stops.map((s) => s.order_id).join(" → ")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}