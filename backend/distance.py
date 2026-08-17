import httpx
from models import Location

OSRM_BASE_URL = "https://router.project-osrm.org"


def build_distance_matrix(locations: list[Location]) -> list[list[float]]:
    coords = ";".join(f"{loc.lng},{loc.lat}" for loc in locations)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords}?annotations=distance"

    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            raise ValueError("OSRM returned non-Ok code")
        return [[d / 1000.0 for d in row] for row in data["distances"]]
    except Exception as e:
        print(f"[OSRM] table request failed, falling back to haversine: {e}")
        return _haversine_matrix(locations)


def build_time_matrix_minutes(locations: list[Location]) -> list[list[int]]:
    coords = ";".join(f"{loc.lng},{loc.lat}" for loc in locations)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords}?annotations=duration"

    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            raise ValueError("OSRM returned non-Ok code")
        return [[round(d / 60) for d in row] for row in data["durations"]]
    except Exception as e:
        print(f"[OSRM] table request failed, falling back to estimate: {e}")
        dist_matrix = _haversine_matrix(locations)
        AVG_SPEED_KMPH = 30
        return [[round((d / AVG_SPEED_KMPH) * 60) for d in row] for row in dist_matrix]


def get_route_geometry(a: Location, b: Location) -> list[list[float]]:
    url = f"{OSRM_BASE_URL}/route/v1/driving/{a.lng},{a.lat};{b.lng},{b.lat}?overview=full&geometries=geojson"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        coords = data["routes"][0]["geometry"]["coordinates"]
        return [[c[1], c[0]] for c in coords]
    except Exception as e:
        print(f"[OSRM] route request failed, falling back to straight line: {e}")
        return [[a.lat, a.lng], [b.lat, b.lng]]


def _haversine_matrix(locations: list[Location]) -> list[list[float]]:
    import math

    def haversine_km(a: Location, b: Location) -> float:
        R = 6371.0
        lat1, lon1 = math.radians(a.lat), math.radians(a.lng)
        lat2, lon2 = math.radians(b.lat), math.radians(b.lng)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    n = len(locations)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine_km(locations[i], locations[j])
    return matrix