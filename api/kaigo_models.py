"""介護事業所 SQLAlchemy モデル定義"""
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Index
from .database import KaigoBase


class KaigoFacility(KaigoBase):
    """介護事業所"""
    __tablename__ = "kaigo_facilities"

    id = Column(String(10), primary_key=True)
    service_code = Column(String(5), primary_key=True)
    service_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    name_kana = Column(Text)
    prefecture_code = Column(String(2), nullable=False, index=True)
    city_code = Column(String(4), nullable=False)
    prefecture_name = Column(Text)
    city_name = Column(Text)
    address = Column(Text)
    address_detail = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(Text)
    fax = Column(Text)
    corporate_number = Column(String(13), index=True)
    corporate_name = Column(Text)
    available_days = Column(Text)  # JSON
    available_days_note = Column(Text)
    capacity = Column(Integer)
    website_url = Column(Text)
    shared_service = Column(Text)
    nursing_care_standard = Column(Text)
    welfare_standard = Column(Text)
    note = Column(Text)
    data_date = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_kaigo_latlng", "latitude", "longitude"),
        Index("idx_kaigo_pref_city", "prefecture_code", "city_code"),
    )


class KaigoServiceMaster(KaigoBase):
    """サービス種別マスタ"""
    __tablename__ = "kaigo_service_master"

    code = Column(String(5), primary_key=True)
    name = Column(Text, nullable=False)
    category = Column(Text)
