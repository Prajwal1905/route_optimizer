from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from models import (
    OptimizeRequest, OptimizeResponse, VehicleRoute, RouteStop, Location,
    BaselineSummary, ComparisonSummary,
)
from distance import build_distance_matrix, build_time_matrix_minutes, get_route_geometry

# Cost model — tune these for your demo/region
FUEL_COST_PER_KM = 12.0      # e.g. INR per km
DRIVER_COST_PER_MIN = 2.0    # e.g. INR per minute of driver time


def _route_cost(distance_km: float, time_minutes: int) -> tuple[float, float, float]:
    fuel_cost = round(distance_km * FUEL_COST_PER_KM, 2)
    driver_cost = round(time_minutes * DRIVER_COST_PER_MIN, 2)
    return fuel_cost, driver_cost, round(fuel_cost + driver_cost, 2)


def solve_vrp(req: OptimizeRequest) -> OptimizeResponse:
    orders = req.orders
    vehicles = req.vehicles

    depot_locations = [v.start_location for v in vehicles]
    order_locations = [o.location for o in orders]
    all_locations: list[Location] = depot_locations + order_locations

    num_vehicles = len(vehicles)
    order_start_idx = num_vehicles

    dist_matrix = build_distance_matrix(all_locations)
    time_matrix = build_time_matrix_minutes(all_locations)

    manager = pywrapcp.RoutingIndexManager(
        len(all_locations),
        num_vehicles,
        list(range(num_vehicles)),
        list(range(num_vehicles)),
    )
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return time_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    demands = [0] * num_vehicles + [o.demand for o in orders]

    def demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        return demands[node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        [v.capacity for v in vehicles],
        True,
        "Capacity",
    )

    routing.AddDimension(
        transit_callback_index,
        30,
        max(v.max_route_minutes for v in vehicles),
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")
    time_dimension.SetGlobalSpanCostCoefficient(100)

    for i, order in enumerate(orders):
        node_index = manager.NodeToIndex(order_start_idx + i)
        if order.time_window_start is not None and order.time_window_end is not None:
            time_dimension.CumulVar(node_index).SetRange(
                order.time_window_start, order.time_window_end
            )

    for i, order in enumerate(orders):
        node_index = manager.NodeToIndex(order_start_idx + i)
        penalty = order.priority * 10000
        routing.AddDisjunction([node_index], penalty)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(search_params)

    routes: list[VehicleRoute] = []
    assigned_order_ids = set()

    if solution:
        for v_idx in range(num_vehicles):
            index = routing.Start(v_idx)
            stops = []
            seq = 0
            total_dist = 0.0
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node >= order_start_idx:
                    order = orders[node - order_start_idx]
                    eta = solution.Value(time_dimension.CumulVar(index))
                    stops.append(RouteStop(order_id=order.id, eta_minutes=eta, sequence=seq))
                    assigned_order_ids.add(order.id)
                    seq += 1
                prev_index = index
                index = solution.Value(routing.NextVar(index))
                prev_node = manager.IndexToNode(prev_index)
                curr_node = manager.IndexToNode(index)
                total_dist += dist_matrix[prev_node][curr_node]

            total_time = solution.Value(time_dimension.CumulVar(routing.End(v_idx)))

            route_geometry: list[list[float]] = []
            if stops:
                orders_by_id = {o.id: o for o in orders}
                sorted_stops = sorted(stops, key=lambda s: s.sequence)
                waypoints = [vehicles[v_idx].start_location] + [
                    orders_by_id[s.order_id].location for s in sorted_stops
                ]
                for i in range(len(waypoints) - 1):
                    segment = get_route_geometry(waypoints[i], waypoints[i + 1])
                    route_geometry.extend(segment)

            fuel_cost, driver_cost, total_cost = _route_cost(total_dist, total_time)

            routes.append(
                VehicleRoute(
                    vehicle_id=vehicles[v_idx].id,
                    stops=stops,
                    total_distance_km=round(total_dist, 2),
                    total_time_minutes=total_time,
                    route_geometry=route_geometry,
                    fuel_cost=fuel_cost,
                    driver_cost=driver_cost,
                    total_cost=total_cost,
                )
            )

    unassigned = [o.id for o in orders if o.id not in assigned_order_ids]

    resp = OptimizeResponse(routes=routes, unassigned_orders=unassigned, conflicts=[])
    resp.comparison = build_comparison(req, resp, dist_matrix, time_matrix)
    return resp


def solve_naive_baseline(
    req: OptimizeRequest,
    dist_matrix: list[list[float]],
    time_matrix: list[list[int]],
) -> BaselineSummary:
    """
    Naive nearest-neighbor baseline: no OR-Tools, no capacity optimization beyond
    a hard skip-if-full check, no time windows, no priority weighting.
    Round-robins orders to whichever vehicle is nearest to its current position,
    same as a dispatcher doing it by hand / a basic greedy script would.
    Used purely to quantify how much OR-Tools improves on "obvious" routing.
    """
    orders = req.orders
    vehicles = req.vehicles
    num_vehicles = len(vehicles)
    order_start_idx = num_vehicles

    remaining = list(range(len(orders)))  # indices into orders
    vehicle_current_node = list(range(num_vehicles))  # start at depot node
    vehicle_load = [0] * num_vehicles
    vehicle_dist = [0.0] * num_vehicles
    vehicle_time = [0] * num_vehicles
    assigned_ids = set()

    # Greedily assign nearest unassigned order to whichever vehicle can reach it soonest
    while remaining:
        best = None  # (time_cost, vehicle_idx, order_idx)
        for v_idx in range(num_vehicles):
            if vehicle_time[v_idx] >= vehicles[v_idx].max_route_minutes:
                continue
            for o_idx in remaining:
                order = orders[o_idx]
                if vehicle_load[v_idx] + order.demand > vehicles[v_idx].capacity:
                    continue
                from_node = vehicle_current_node[v_idx]
                to_node = order_start_idx + o_idx
                t = time_matrix[from_node][to_node]
                if best is None or t < best[0]:
                    best = (t, v_idx, o_idx)
        if best is None:
            break  # nothing left can be assigned (capacity/time exhausted)

        _, v_idx, o_idx = best
        order = orders[o_idx]
        from_node = vehicle_current_node[v_idx]
        to_node = order_start_idx + o_idx

        vehicle_dist[v_idx] += dist_matrix[from_node][to_node]
        vehicle_time[v_idx] += time_matrix[from_node][to_node]
        vehicle_load[v_idx] += order.demand
        vehicle_current_node[v_idx] = to_node

        assigned_ids.add(order.id)
        remaining.remove(o_idx)

    # Add return-to-depot leg for each vehicle that made at least one stop,
    # so this is a fair comparison against the OR-Tools route (which also
    # returns to depot at the end).
    for v_idx in range(num_vehicles):
        if vehicle_current_node[v_idx] != v_idx:  # moved away from depot
            depot_node = v_idx
            last_node = vehicle_current_node[v_idx]
            vehicle_dist[v_idx] += dist_matrix[last_node][depot_node]
            vehicle_time[v_idx] += time_matrix[last_node][depot_node]

    total_distance = round(sum(vehicle_dist), 2)
    total_time = round(sum(vehicle_time))
    unassigned_count = len(orders) - len(assigned_ids)

    fuel_cost, driver_cost, total_cost = _route_cost(total_distance, total_time)

    return BaselineSummary(
        total_distance_km=total_distance,
        total_time_minutes=total_time,
        total_cost=total_cost,
        unassigned_count=unassigned_count,
    )


def build_comparison(
    req: OptimizeRequest,
    resp: OptimizeResponse,
    dist_matrix: list[list[float]],
    time_matrix: list[list[int]],
) -> ComparisonSummary:
    baseline = solve_naive_baseline(req, dist_matrix, time_matrix)

    opt_distance = round(sum(r.total_distance_km for r in resp.routes), 2)
    opt_time = round(sum(r.total_time_minutes for r in resp.routes))
    opt_cost = round(sum(r.total_cost for r in resp.routes), 2)
    optimized = BaselineSummary(
        total_distance_km=opt_distance,
        total_time_minutes=opt_time,
        total_cost=opt_cost,
        unassigned_count=len(resp.unassigned_orders),
    )

    def pct_saved(before: float, after: float) -> float:
        if before <= 0:
            return 0.0
        return round(((before - after) / before) * 100, 1)

    return ComparisonSummary(
        baseline=baseline,
        optimized=optimized,
        distance_saved_km=round(baseline.total_distance_km - optimized.total_distance_km, 2),
        distance_saved_pct=pct_saved(baseline.total_distance_km, optimized.total_distance_km),
        time_saved_minutes=baseline.total_time_minutes - optimized.total_time_minutes,
        time_saved_pct=pct_saved(baseline.total_time_minutes, optimized.total_time_minutes),
        cost_saved=round(baseline.total_cost - optimized.total_cost, 2),
        cost_saved_pct=pct_saved(baseline.total_cost, optimized.total_cost),
    )