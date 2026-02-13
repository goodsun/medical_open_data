"""介護事業所エンドポイント"""
import json
import math
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_kaigo_db
from ..kaigo_schemas import (
    KaigoFacilityListOut, KaigoFacilityDetailOut, KaigoListResponse,
    PaginationOut, KaigoStatsOut, KaigoServiceMasterOut,
)
from ..services.kaigo_search import (
    search_kaigo, search_kaigo_nearby, get_kaigo_detail,
    get_kaigo_services, get_kaigo_stats,
)

router = APIRouter(prefix="/api/v1/kaigo", tags=["kaigo"])


def _parse_days(fac) -> Optional[dict]:
    if fac.available_days:
        try:
            return json.loads(fac.available_days) if isinstance(fac.available_days, str) else fac.available_days
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _to_list(fac, distance_km=None) -> KaigoFacilityListOut:
    return KaigoFacilityListOut(
        id=fac.id,
        service_code=fac.service_code,
        service_type=fac.service_type,
        name=fac.name,
        prefecture_code=fac.prefecture_code,
        prefecture_name=fac.prefecture_name,
        city_code=fac.city_code,
        city_name=fac.city_name,
        address=fac.address,
        latitude=fac.latitude,
        longitude=fac.longitude,
        phone=fac.phone,
        corporate_name=fac.corporate_name,
        capacity=fac.capacity,
        available_days=_parse_days(fac),
        distance_km=distance_km,
    )


@router.get("", response_model=KaigoListResponse)
def list_kaigo(
    q: Optional[str] = Query(None, description="フリーワード（名称・住所）"),
    service: Optional[str] = Query(None, description="サービス種別名またはコード"),
    prefecture: Optional[str] = Query(None, description="都道府県コード (01-47)"),
    city: Optional[str] = Query(None, description="市区町村コード"),
    corporate_number: Optional[str] = Query(None, description="法人番号"),
    available_day: Optional[str] = Query(None, description="利用可能曜日 (mon/tue/.../sun/holiday)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_kaigo_db),
):
    facilities, total = search_kaigo(
        db, q=q, service=service, prefecture=prefecture, city=city,
        corporate_number=corporate_number, available_day=available_day,
        page=page, per_page=per_page,
    )
    return KaigoListResponse(
        data=[_to_list(f) for f in facilities],
        pagination=PaginationOut(
            page=page, per_page=per_page, total=total,
            pages=math.ceil(total / per_page) if per_page else 0,
        ),
    )


@router.get("/nearby", response_model=List[KaigoFacilityListOut])
def nearby_kaigo(
    lat: float = Query(..., description="緯度"),
    lng: float = Query(..., description="経度"),
    radius: float = Query(5.0, ge=0.1, le=50, description="半径 (km)"),
    service: Optional[str] = Query(None, description="サービス種別名またはコード"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_kaigo_db),
):
    results = search_kaigo_nearby(db, lat=lat, lng=lng, radius_km=radius, service=service, limit=limit)
    return [_to_list(fac, dist) for fac, dist in results]


@router.get("/services", response_model=List[KaigoServiceMasterOut])
def kaigo_services(db: Session = Depends(get_kaigo_db)):
    return get_kaigo_services(db)


@router.get("/stats", response_model=KaigoStatsOut)
def kaigo_stats(db: Session = Depends(get_kaigo_db)):
    return get_kaigo_stats(db)


@router.get("/{facility_id}", response_model=List[KaigoFacilityDetailOut])
def kaigo_detail(facility_id: str, db: Session = Depends(get_kaigo_db)):
    facilities = get_kaigo_detail(db, facility_id)
    if not facilities:
        raise HTTPException(status_code=404, detail="事業所が見つかりません")
    result = []
    for fac in facilities:
        result.append(KaigoFacilityDetailOut(
            id=fac.id,
            service_code=fac.service_code,
            service_type=fac.service_type,
            name=fac.name,
            name_kana=fac.name_kana,
            prefecture_code=fac.prefecture_code,
            prefecture_name=fac.prefecture_name,
            city_code=fac.city_code,
            city_name=fac.city_name,
            address=fac.address,
            address_detail=fac.address_detail,
            latitude=fac.latitude,
            longitude=fac.longitude,
            phone=fac.phone,
            fax=fac.fax,
            corporate_number=fac.corporate_number,
            corporate_name=fac.corporate_name,
            available_days=_parse_days(fac),
            available_days_note=fac.available_days_note,
            capacity=fac.capacity,
            website_url=fac.website_url,
            shared_service=fac.shared_service,
            nursing_care_standard=fac.nursing_care_standard,
            welfare_standard=fac.welfare_standard,
            note=fac.note,
            data_date=fac.data_date,
        ))
    return result
