"""位置計算ユーティリティ — DB非依存のhaversine実装"""
import math

EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の距離をkmで返す（haversine公式）"""
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_km: float):
    """矩形バウンディングボックスを返す（粗いフィルタ用）"""
    dlat = radius_km / 111.0  # 1度≈111km
    dlng = radius_km / (111.0 * math.cos(math.radians(lat)))
    return {
        "min_lat": lat - dlat,
        "max_lat": lat + dlat,
        "min_lng": lng - dlng,
        "max_lng": lng + dlng,
    }
