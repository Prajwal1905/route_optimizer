from models import OptimizeResponse, OptimizeRequest


def detect_conflicts(req: OptimizeRequest, resp: OptimizeResponse) -> list[str]:
    conflicts = []

    
    seen = {}
    for route in resp.routes:
        for stop in route.stops:
            if stop.order_id in seen:
                conflicts.append(
                    f"Order {stop.order_id} assigned to both {seen[stop.order_id]} and {route.vehicle_id}"
                )
            else:
                seen[stop.order_id] = route.vehicle_id

    
    orders_by_id = {o.id: o for o in req.orders}
    vehicles_by_id = {v.id: v for v in req.vehicles}
    for route in resp.routes:
        total_demand = sum(orders_by_id[s.order_id].demand for s in route.stops)
        cap = vehicles_by_id[route.vehicle_id].capacity
        if total_demand > cap:
            conflicts.append(
                f"Vehicle {route.vehicle_id} overloaded: {total_demand}/{cap}"
            )

    for route in resp.routes:
        max_minutes = vehicles_by_id[route.vehicle_id].max_route_minutes
        if route.total_time_minutes > max_minutes:
            conflicts.append(
                f"Vehicle {route.vehicle_id} exceeds shift time: "
                f"{route.total_time_minutes}/{max_minutes} min"
            )

    
    for order_id in resp.unassigned_orders:
        order = orders_by_id[order_id]
        if order.priority >= 3:
            conflicts.append(f"High priority order {order_id} could not be assigned")

    return conflicts