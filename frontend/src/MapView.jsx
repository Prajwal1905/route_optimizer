import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const COLORS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0"];

export default function MapView({ orders, vehicles, routes }) {
  const center = vehicles.length
    ? [vehicles[0].start_location.lat, vehicles[0].start_location.lng]
    : [19.076, 72.8777];

  const orderById = Object.fromEntries(orders.map((o) => [o.id, o]));
  const vehicleById = Object.fromEntries(vehicles.map((v) => [v.id, v]));

  return (
    <MapContainer center={center} zoom={12} style={{ height: "600px", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {vehicles.map((v) => (
        <Marker key={v.id} position={[v.start_location.lat, v.start_location.lng]}>
          <Popup>Vehicle {v.id} (start)</Popup>
        </Marker>
      ))}

      {orders.map((o) => (
        <Marker key={o.id} position={[o.location.lat, o.location.lng]}>
          <Popup>
            Order {o.id} <br />
            Priority: {o.priority}
          </Popup>
        </Marker>
      ))}

      {routes.map((route, idx) => {
        const vehicle = vehicleById[route.vehicle_id];
        if (!vehicle || route.stops.length === 0) return null;

        const path = [
          [vehicle.start_location.lat, vehicle.start_location.lng],
          ...route.stops
            .sort((a, b) => a.sequence - b.sequence)
            .map((s) => {
              const o = orderById[s.order_id];
              return [o.location.lat, o.location.lng];
            }),
        ];

        return (
          <Polyline
            key={route.vehicle_id}
            positions={path}
            color={COLORS[idx % COLORS.length]}
            weight={4}
          />
        );
      })}
    </MapContainer>
  );
}