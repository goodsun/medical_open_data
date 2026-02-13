"""DCAT カタログエンドポイント — データスペース連携用メタデータ"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Facility

router = APIRouter(tags=["catalog"])

BASE_URL = "https://mods.bon-soleil.com"


@router.get("/api/v1/catalog")
def dcat_catalog(db: Session = Depends(get_db)):
    """DCAT-AP準拠のデータカタログ（JSON-LD）"""
    total = db.query(func.count(Facility.id)).scalar()
    latest_date = db.query(func.max(Facility.data_date)).scalar()

    return {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "vcard": "http://www.w3.org/2006/vcard/ns#",
        },
        "@type": "dcat:Catalog",
        "dct:title": "MODS — Medical Open Data Search",
        "dct:description": "厚生労働省オープンデータを活用した全国医療施設検索API",
        "dct:language": "ja",
        "dct:publisher": {
            "@type": "foaf:Agent",
            "foaf:name": "MODS Project",
        },
        "dcat:dataset": [
            {
                "@type": "dcat:Dataset",
                "dct:title": "全国医療施設データ",
                "dct:description": f"全国{total:,}件の病院・診療所・歯科・助産所・薬局の施設情報、診療科、診療時間",
                "dct:source": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html",
                "dct:temporal": str(latest_date) if latest_date else None,
                "dct:accrualPeriodicity": "半年（6月・12月更新）",
                "dct:spatial": "日本全国（47都道府県）",
                "dcat:distribution": [
                    {
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": f"{BASE_URL}/api/v1/facilities",
                        "dct:format": "application/json",
                        "dct:title": "施設検索API",
                    },
                    {
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": f"{BASE_URL}/api/v1/facilities/nearby",
                        "dct:format": "application/json",
                        "dct:title": "近隣検索API",
                    },
                    {
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": f"{BASE_URL}/openapi.json",
                        "dct:format": "application/json",
                        "dct:title": "OpenAPI仕様",
                    },
                ],
            }
        ],
    }
