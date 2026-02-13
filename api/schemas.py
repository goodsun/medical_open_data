"""Pydantic スキーマ定義"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# === レスポンス ===

class PrefectureOut(BaseModel):
    code: str
    name: str
    class Config:
        from_attributes = True


class SpecialtyMasterOut(BaseModel):
    code: str
    name: str
    category: Optional[str] = None
    class Config:
        from_attributes = True


class SpecialtyOut(BaseModel):
    specialty_code: Optional[str] = None
    specialty_name: str
    time_slot: Optional[str] = None
    schedule: Dict[str, Any]
    reception: Optional[Dict[str, Any]] = None
    class Config:
        from_attributes = True


class BedOut(BaseModel):
    general: Optional[int] = None
    recuperation: Optional[int] = None
    psychiatric: Optional[int] = None
    tuberculosis: Optional[int] = None
    infectious: Optional[int] = None
    total: Optional[int] = None
    class Config:
        from_attributes = True


class FacilityListOut(BaseModel):
    """一覧用（軽量）"""
    id: str
    facility_type: int
    name: str
    prefecture_code: str
    prefecture_name: Optional[str] = None
    city_code: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website_url: Optional[str] = None
    distance_km: Optional[float] = None  # 近隣検索時のみ
    class Config:
        from_attributes = True


class FacilityDetailOut(BaseModel):
    """詳細用"""
    id: str
    facility_type: int
    name: str
    name_kana: Optional[str] = None
    name_en: Optional[str] = None
    prefecture_code: str
    prefecture_name: Optional[str] = None
    city_code: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website_url: Optional[str] = None
    closed_holiday: Optional[bool] = None
    closed_other: Optional[str] = None
    closed_weekly: Optional[Dict[str, bool]] = None
    specialities: List[SpecialtyOut] = []
    beds: Optional[BedOut] = None
    class Config:
        from_attributes = True


class PaginationOut(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class FacilityListResponse(BaseModel):
    data: List[FacilityListOut]
    pagination: PaginationOut


class StatsOut(BaseModel):
    total_facilities: int
    by_type: Dict[str, int]
    by_prefecture: Dict[str, int]
    total_specialities: int
