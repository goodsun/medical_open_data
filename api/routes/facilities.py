"""施設エンドポイント"""
import json
import math
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    FacilityListOut, FacilityDetailOut, FacilityListResponse,
    PaginationOut, SpecialtyOut, BedOut, StatsOut,
    PrefectureOut, SpecialtyMasterOut,
)
from ..services.search import (
    search_facilities, search_nearby, get_facility_detail, get_stats,
    FACILITY_TYPE_NAMES,
)
from ..models import Prefecture, SpecialtyMaster

router = APIRouter(prefix="/api/v1", tags=["facilities"])


def _facility_to_list(fac, distance_km=None) -> FacilityListOut:
    pref_name = fac.prefecture.name if fac.prefecture else None
    return FacilityListOut(
        id=fac.id,
        facility_type=fac.facility_type,
        name=fac.name,
        prefecture_code=fac.prefecture_code,
        prefecture_name=pref_name,
        city_code=fac.city_code,
        address=fac.address,
        latitude=fac.latitude,
        longitude=fac.longitude,
        website_url=fac.website_url,
        distance_km=distance_km,
    )


@router.get("/facilities", response_model=FacilityListResponse)
def list_facilities(
    q: Optional[str] = Query(None, description="フリーワード（名称・住所）"),
    type: Optional[List[int]] = Query(None, description="施設種別 (1:病院 2:診療所 3:歯科 4:助産所 5:薬局)"),
    prefecture: Optional[str] = Query(None, description="都道府県コード (01-47)"),
    city: Optional[str] = Query(None, description="市区町村コード"),
    specialty: Optional[str] = Query(None, description="診療科名（部分一致）またはコード"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    facilities, total = search_facilities(
        db, q=q, facility_types=type,
        prefecture=prefecture, city=city, specialty=specialty,
        page=page, per_page=per_page,
    )

    return FacilityListResponse(
        data=[_facility_to_list(f) for f in facilities],
        pagination=PaginationOut(
            page=page,
            per_page=per_page,
            total=total,
            pages=math.ceil(total / per_page) if per_page else 0,
        ),
    )


@router.get("/facilities/nearby", response_model=List[FacilityListOut])
def nearby_facilities(
    lat: float = Query(..., description="緯度"),
    lng: float = Query(..., description="経度"),
    radius: float = Query(5.0, ge=0.1, le=50, description="半径 (km)"),
    type: Optional[List[int]] = Query(None, description="施設種別"),
    specialty: Optional[str] = Query(None, description="診療科名"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    results = search_nearby(
        db, lat=lat, lng=lng, radius_km=radius,
        facility_types=type, specialty=specialty, limit=limit,
    )
    return [_facility_to_list(fac, dist) for fac, dist in results]


@router.get("/facilities/{facility_id}", response_model=FacilityDetailOut)
def facility_detail(facility_id: str, db: Session = Depends(get_db)):
    fac = get_facility_detail(db, facility_id)
    if not fac:
        raise HTTPException(status_code=404, detail="施設が見つかりません")

    pref_name = fac.prefecture.name if fac.prefecture else None

    return FacilityDetailOut(
        id=fac.id,
        facility_type=fac.facility_type,
        name=fac.name,
        name_kana=fac.name_kana,
        name_en=fac.name_en,
        prefecture_code=fac.prefecture_code,
        prefecture_name=pref_name,
        city_code=fac.city_code,
        address=fac.address,
        latitude=fac.latitude,
        longitude=fac.longitude,
        website_url=fac.website_url,
        closed_holiday=fac.closed_holiday,
        closed_other=fac.closed_other,
        closed_weekly=fac.closed_weekly,
        specialities=[SpecialtyOut(
            specialty_code=s.specialty_code,
            specialty_name=s.specialty_name,
            time_slot=s.time_slot,
            schedule=json.loads(s.schedule) if isinstance(s.schedule, str) else s.schedule,
            reception=json.loads(s.reception) if isinstance(s.reception, str) else s.reception,
        ) for s in fac.specialities],
        beds=BedOut.model_validate(fac.beds) if fac.beds else None,
    )


@router.get("/specialities", response_model=List[SpecialtyMasterOut])
def list_specialities(
    category: Optional[str] = Query(None, description="カテゴリ（内科系, 外科系, etc）"),
    db: Session = Depends(get_db),
):
    query = db.query(SpecialtyMaster)
    if category:
        query = query.filter(SpecialtyMaster.category == category)
    return query.order_by(SpecialtyMaster.code).all()


@router.get("/prefectures", response_model=List[PrefectureOut])
def list_prefectures(db: Session = Depends(get_db)):
    return db.query(Prefecture).order_by(Prefecture.code).all()


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    return get_stats(db)


@router.get("/health")
def health():
    return {"status": "ok"}
