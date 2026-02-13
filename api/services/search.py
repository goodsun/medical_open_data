"""検索サービス"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from ..models import Facility, Specialty, Prefecture
from .geo import haversine, bounding_box

FACILITY_TYPE_NAMES = {1: "病院", 2: "診療所", 3: "歯科", 4: "助産所", 5: "薬局"}


def search_facilities(
    db: Session,
    q: Optional[str] = None,
    facility_types: Optional[List[int]] = None,
    prefecture: Optional[str] = None,
    city: Optional[str] = None,
    specialty: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[Facility], int]:
    """施設検索"""
    query = db.query(Facility)

    # フリーワード（名称・住所）
    if q:
        query = query.filter(
            or_(
                Facility.name.contains(q),
                Facility.name_kana.contains(q),
                Facility.address.contains(q),
            )
        )

    # 施設種別
    if facility_types:
        query = query.filter(Facility.facility_type.in_(facility_types))

    # 都道府県
    if prefecture:
        query = query.filter(Facility.prefecture_code == prefecture)

    # 市区町村
    if city:
        query = query.filter(Facility.city_code == city)

    # 診療科
    if specialty:
        query = query.join(Facility.specialities).filter(
            or_(
                Specialty.specialty_name.contains(specialty),
                Specialty.specialty_code == specialty,
            )
        ).distinct()

    total = query.count()
    facilities = query.offset((page - 1) * per_page).limit(per_page).all()

    return facilities, total


def search_nearby(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    facility_types: Optional[List[int]] = None,
    specialty: Optional[str] = None,
    limit: int = 20,
) -> List[Tuple[Facility, float]]:
    """近隣検索 — バウンディングボックス→haversine精密計算"""

    bbox = bounding_box(lat, lng, radius_km)

    query = db.query(Facility).filter(
        Facility.latitude.isnot(None),
        Facility.longitude.isnot(None),
        Facility.latitude >= bbox["min_lat"],
        Facility.latitude <= bbox["max_lat"],
        Facility.longitude >= bbox["min_lng"],
        Facility.longitude <= bbox["max_lng"],
    )

    if facility_types:
        query = query.filter(Facility.facility_type.in_(facility_types))

    if specialty:
        query = query.join(Facility.specialities).filter(
            Specialty.specialty_name.contains(specialty)
        ).distinct()

    candidates = query.all()

    # haversineで精密距離計算
    results = []
    for fac in candidates:
        dist = haversine(lat, lng, fac.latitude, fac.longitude)
        if dist <= radius_km:
            results.append((fac, round(dist, 2)))

    # 距離順ソート
    results.sort(key=lambda x: x[1])
    return results[:limit]


def get_facility_detail(db: Session, facility_id: str) -> Optional[Facility]:
    """施設詳細"""
    return (
        db.query(Facility)
        .options(
            joinedload(Facility.specialities),
            joinedload(Facility.beds),
            joinedload(Facility.prefecture),
        )
        .filter(Facility.id == facility_id)
        .first()
    )


def get_stats(db: Session) -> dict:
    """統計情報"""
    total = db.query(func.count(Facility.id)).scalar()

    by_type = {}
    for type_id, type_name in FACILITY_TYPE_NAMES.items():
        count = db.query(func.count(Facility.id)).filter(
            Facility.facility_type == type_id
        ).scalar()
        by_type[type_name] = count

    by_pref = {}
    pref_counts = (
        db.query(Prefecture.name, func.count(Facility.id))
        .join(Facility, Facility.prefecture_code == Prefecture.code)
        .group_by(Prefecture.name)
        .all()
    )
    for name, count in pref_counts:
        by_pref[name] = count

    total_specs = db.query(func.count(Specialty.id)).scalar()

    return {
        "total_facilities": total,
        "by_type": by_type,
        "by_prefecture": by_pref,
        "total_specialities": total_specs,
    }
