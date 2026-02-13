"""介護事業所 Pydantic スキーマ定義"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class KaigoFacilityListOut(BaseModel):
    id: str
    service_code: str
    service_type: str
    name: str
    prefecture_code: str
    prefecture_name: Optional[str] = None
    city_code: str
    city_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    corporate_name: Optional[str] = None
    capacity: Optional[int] = None
    available_days: Optional[Dict[str, bool]] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class KaigoFacilityDetailOut(BaseModel):
    id: str
    service_code: str
    service_type: str
    name: str
    name_kana: Optional[str] = None
    prefecture_code: str
    prefecture_name: Optional[str] = None
    city_code: str
    city_name: Optional[str] = None
    address: Optional[str] = None
    address_detail: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    corporate_number: Optional[str] = None
    corporate_name: Optional[str] = None
    available_days: Optional[Dict[str, bool]] = None
    available_days_note: Optional[str] = None
    capacity: Optional[int] = None
    website_url: Optional[str] = None
    shared_service: Optional[str] = None
    nursing_care_standard: Optional[str] = None
    welfare_standard: Optional[str] = None
    note: Optional[str] = None
    data_date: Optional[str] = None

    class Config:
        from_attributes = True


class KaigoServiceMasterOut(BaseModel):
    code: str
    name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


class PaginationOut(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class KaigoListResponse(BaseModel):
    data: List[KaigoFacilityListOut]
    pagination: PaginationOut


class KaigoStatsOut(BaseModel):
    total_facilities: int
    unique_facilities: int
    by_service: Dict[str, int]
    by_category: Dict[str, int]
    by_prefecture: Dict[str, int]
