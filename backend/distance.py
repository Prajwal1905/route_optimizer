import math
from models import Location

AVG_SPEED_KMPH = 30  


def haversine_km(a: Location, b: Location) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a.lat), math.radians(a.lng)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lng)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def build_distance_matrix(locations: list[Location]) -> list[list[float]]:
    
    n = len(locations)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine_km(locations[i], locations[j])
    return matrix


def build_time_matrix_minutes(distance_matrix: list[list[float]]) -> list[list[int]]:
    
    return [
        [round((d / AVG_SPEED_KMPH) * 60) for d in row]
        for row in distance_matrix
    ]