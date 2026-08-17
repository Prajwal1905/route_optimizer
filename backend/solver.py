from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from models import OptimizeRequest, OptimizeResponse, VehicleRoute, RouteStop, Location
from distance import build_distance_matrix, build_time_matrix_minutes, get_route_geometry


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

            routes.append(
                VehicleRoute(
                    vehicle_id=vehicles[v_idx].id,
                    stops=stops,
                    total_distance_km=round(total_dist, 2),
                    total_time_minutes=total_time,
                    route_geometry=route_geometry,
                )
            )

    unassigned = [o.id for o in orders if o.id not in assigned_order_ids]

    return OptimizeResponse(routes=routes, unassigned_orders=unassigned, conflicts=[])