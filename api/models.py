"""SQLAlchemy モデル定義"""
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, SmallInteger, Integer, Float, Boolean,
    Date, DateTime, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from .database import Base


class Prefecture(Base):
    """都道府県マスタ"""
    __tablename__ = "prefectures"

    code = Column(String(2), primary_key=True)
    name = Column(String(4), nullable=False)

    facilities = relationship("Facility", back_populates="prefecture")


class City(Base):
    """市区町村マスタ"""
    __tablename__ = "cities"

    prefecture_code = Column(String(2), ForeignKey("prefectures.code"), primary_key=True)
    code = Column(String(3), primary_key=True)
    name = Column(Text, nullable=False)

    prefecture = relationship("Prefecture")


class SpecialtyMaster(Base):
    """診療科マスタ（正規コードのみ）"""
    __tablename__ = "specialty_master"

    code = Column(String(10), primary_key=True)
    name = Column(Text, nullable=False)
    category = Column(String(50))  # 内科系, 外科系, etc.


class Facility(Base):
    """医療施設"""
    __tablename__ = "facilities"

    id = Column(String(13), primary_key=True)  # 厚労省ID
    facility_type = Column(SmallInteger, nullable=False, index=True)
    # 1:病院 2:診療所 3:歯科 4:助産所 5:薬局
    name = Column(Text, nullable=False)
    name_kana = Column(Text)
    name_short = Column(Text)
    name_en = Column(Text)
    prefecture_code = Column(String(2), ForeignKey("prefectures.code"), nullable=False, index=True)
    city_code = Column(String(3), nullable=False)
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    website_url = Column(Text)
    closed_holiday = Column(Boolean)  # 祝日休診
    closed_other = Column(Text)       # その他休診日
    closed_weekly = Column(JSON)      # {"mon":true,"tue":false,...}
    closed_weeks = Column(JSON)       # {"week1":{"mon":true,...},...}
    raw_data = Column(JSON)           # 種別固有の全カラム
    data_date = Column(Date)          # データ基準日
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prefecture = relationship("Prefecture", back_populates="facilities")
    specialities = relationship("Specialty", back_populates="facility", cascade="all, delete-orphan")
    beds = relationship("HospitalBed", back_populates="facility", uselist=False, cascade="all, delete-orphan")
    business_hours = relationship("BusinessHour", back_populates="facility", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_facilities_latlng", "latitude", "longitude"),
        Index("idx_facilities_pref_city", "prefecture_code", "city_code"),
    )


class Specialty(Base):
    """診療科・診療時間"""
    __tablename__ = "specialities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(String(13), ForeignKey("facilities.id"), nullable=False, index=True)
    specialty_code = Column(String(10), index=True)
    specialty_name = Column(Text, nullable=False)
    time_slot = Column(String(10))  # 診療時間帯
    schedule = Column(JSON, nullable=False)    # 曜日別診療時間
    reception = Column(JSON)                    # 曜日別受付時間

    facility = relationship("Facility", back_populates="specialities")

    __table_args__ = (
        Index("idx_specialities_name", "specialty_name"),
    )


class HospitalBed(Base):
    """病床情報"""
    __tablename__ = "hospital_beds"

    facility_id = Column(String(13), ForeignKey("facilities.id"), primary_key=True)
    general = Column(Integer)            # 一般病床
    recuperation = Column(Integer)       # 療養病床
    recuperation_medical = Column(Integer)  # 療養（医療保険）
    recuperation_nursing = Column(Integer)  # 療養（介護保険）
    psychiatric = Column(Integer)        # 精神病床
    tuberculosis = Column(Integer)       # 結核病床
    infectious = Column(Integer)         # 感染症病床
    total = Column(Integer)              # 合計

    facility = relationship("Facility", back_populates="beds")


class BusinessHour(Base):
    """営業時間帯（助産所・薬局用）"""
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(String(13), ForeignKey("facilities.id"), nullable=False, index=True)
    slot_number = Column(SmallInteger, nullable=False)  # 1-4
    hour_type = Column(String(20), nullable=False)      # "business" / "reception"
    schedule = Column(JSON, nullable=False)              # 曜日別の開始/終了時間

    facility = relationship("Facility", back_populates="business_hours")
