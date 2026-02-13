"""DCAT カタログエンドポイント — データスペース連携用メタデータ"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db, get_kaigo_db
from ..models import Facility

router = APIRouter(tags=["catalog"])

BASE_URL = "https://mods.bon-soleil.com"


@router.get("/api/v1/catalog")
def dcat_catalog(db: Session = Depends(get_db), kaigo_db: Session = Depends(get_kaigo_db)):
    """DCAT-AP準拠のデータカタログ（JSON-LD）"""
    total = db.query(func.count(Facility.id)).scalar()
    latest_date = db.query(func.max(Facility.data_date)).scalar()

    # 介護データ統計
    from sqlalchemy import text
    try:
        kaigo_total = kaigo_db.execute(text("SELECT count(*) FROM kaigo_facilities")).scalar()
    except Exception:
        kaigo_total = 0

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
            },
            {
                "@type": "dcat:Dataset",
                "dct:title": "全国介護事業所データ",
                "dct:description": f"全国{kaigo_total:,}件の介護事業所情報（35サービス種別）",
                "dct:source": "https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html",
                "dct:accrualPeriodicity": "半年（6月・12月更新）",
                "dct:spatial": "日本全国（47都道府県）",
                "dcat:distribution": [
                    {
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": f"{BASE_URL}/api/v1/kaigo",
                        "dct:format": "application/json",
                        "dct:title": "介護事業所検索API",
                    },
                    {
                        "@type": "dcat:Distribution",
                        "dcat:accessURL": f"{BASE_URL}/api/v1/kaigo/nearby",
                        "dct:format": "application/json",
                        "dct:title": "介護事業所近隣検索API",
                    },
                ],
            },
        ],
    }
