"""介護事業所検索サービス"""
import json
import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text

from ..kaigo_models import KaigoFacility, KaigoServiceMaster
from .geo import haversine, bounding_box

logger = logging.getLogger(__name__)


def _kaigo_fts_search(db: Session, query: str, limit: int = 1000) -> list:
    """介護FTS5検索。(id, service_code)タプルのリストを返す"""
    import unicodedata
    normalized = unicodedata.normalize("NFKC", query)
    terms = normalized.strip().split()

    if any(len(t) < 3 for t in terms):
        return []

    fts_query = " AND ".join(f'"{t}"' for t in terms if t)
    if not fts_query:
        return []

    try:
        exists = db.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kaigo_facilities_fts'"
        )).fetchone()
        if not exists:
            return []

        rows = db.execute(
            text("SELECT facility_id FROM kaigo_facilities_fts WHERE kaigo_facilities_fts MATCH :q LIMIT :lim"),
            {"q": fts_query, "lim": limit}
        ).fetchall()
        # facility_id = "id:service_code"
        result = []
        for r in rows:
            parts = r[0].split(":", 1)
            if len(parts) == 2:
                result.append((parts[0], parts[1]))
        return result
    except Exception as e:
        logger.warning(f"Kaigo FTS5 search failed: {e}")
        return []


def search_kaigo(
    db: Session,
    q: Optional[str] = None,
    service: Optional[str] = None,
    prefecture: Optional[str] = None,
    city: Optional[str] = None,
    corporate_number: Optional[str] = None,
    available_day: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[KaigoFacility], int]:
    """介護事業所検索"""
    query = db.query(KaigoFacility)

    if q:
        fts_results = _kaigo_fts_search(db, q)
        if fts_results:
            # Build OR conditions for composite keys
            from sqlalchemy import tuple_
            query = query.filter(
                tuple_(KaigoFacility.id, KaigoFacility.service_code).in_(fts_results)
            )
        else:
            query = query.filter(
                or_(
                    KaigoFacility.name.contains(q),
                    KaigoFacility.name_kana.contains(q),
                    KaigoFacility.address.contains(q),
                )
            )

    if service:
        # サービスコードまたはサービス名で検索
        if service.isdigit():
            query = query.filter(KaigoFacility.service_code == service)
        else:
            query = query.filter(KaigoFacility.service_type.contains(service))

    if prefecture:
        query = query.filter(KaigoFacility.prefecture_code == prefecture)

    if city:
        query = query.filter(KaigoFacility.city_code == city)

    if corporate_number:
        query = query.filter(KaigoFacility.corporate_number == corporate_number)

    if available_day:
        # JSON内の曜日キーで検索
        day_key = f'"{available_day}":true' if available_day != "true" else available_day
        # SQLite JSON検索
        query = query.filter(KaigoFacility.available_days.contains(f'"{available_day}": true').self_group() |
                             KaigoFacility.available_days.contains(f'"{available_day}":true'))

    total = query.count()
    facilities = query.offset((page - 1) * per_page).limit(per_page).all()
    return facilities, total


def search_kaigo_nearby(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    service: Optional[str] = None,
    limit: int = 20,
) -> List[Tuple[KaigoFacility, float]]:
    """介護事業所近隣検索"""
    bbox = bounding_box(lat, lng, radius_km)

    query = db.query(KaigoFacility).filter(
        KaigoFacility.latitude.isnot(None),
        KaigoFacility.longitude.isnot(None),
        KaigoFacility.latitude >= bbox["min_lat"],
        KaigoFacility.latitude <= bbox["max_lat"],
        KaigoFacility.longitude >= bbox["min_lng"],
        KaigoFacility.longitude <= bbox["max_lng"],
    )

    if service:
        if service.isdigit():
            query = query.filter(KaigoFacility.service_code == service)
        else:
            query = query.filter(KaigoFacility.service_type.contains(service))

    candidates = query.all()

    results = []
    for fac in candidates:
        dist = haversine(lat, lng, fac.latitude, fac.longitude)
        if dist <= radius_km:
            results.append((fac, round(dist, 2)))

    results.sort(key=lambda x: x[1])
    return results[:limit]


def get_kaigo_detail(db: Session, facility_id: str) -> List[KaigoFacility]:
    """事業所詳細（同一IDで複数サービスの場合リストで返す）"""
    return db.query(KaigoFacility).filter(KaigoFacility.id == facility_id).all()


def get_kaigo_services(db: Session) -> List[KaigoServiceMaster]:
    """サービス種別マスタ一覧"""
    return db.query(KaigoServiceMaster).order_by(KaigoServiceMaster.code).all()


def get_kaigo_stats(db: Session) -> dict:
    """統計情報"""
    total = db.query(func.count()).select_from(KaigoFacility).scalar()
    unique = db.execute(text("SELECT count(DISTINCT id) FROM kaigo_facilities")).scalar()

    by_service = {}
    rows = (
        db.query(KaigoFacility.service_type, func.count())
        .group_by(KaigoFacility.service_type)
        .order_by(func.count().desc())
        .all()
    )
    for name, count in rows:
        by_service[name] = count

    by_category = {}
    cat_rows = (
        db.query(KaigoServiceMaster.category, func.count())
        .join(KaigoFacility, KaigoFacility.service_code == KaigoServiceMaster.code)
        .group_by(KaigoServiceMaster.category)
        .all()
    )
    for cat, count in cat_rows:
        by_category[cat or "不明"] = count

    by_pref = {}
    pref_rows = (
        db.query(KaigoFacility.prefecture_name, func.count())
        .group_by(KaigoFacility.prefecture_name)
        .order_by(func.count().desc())
        .all()
    )
    for name, count in pref_rows:
        by_pref[name or "不明"] = count

    return {
        "total_facilities": total,
        "unique_facilities": unique,
        "by_service": by_service,
        "by_category": by_category,
        "by_prefecture": by_pref,
    }
