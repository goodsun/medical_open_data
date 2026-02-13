# 設計書 — medical_open_data

## 1. 概要

厚労省オープンデータ（医療情報ネット）をDB化し、REST API + Web UIで検索可能にする。
国税庁法人番号との紐付けにより、データスペース接続の基盤を提供。

**本番URL:** https://mods.bon-soleil.com/

## 2. 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| API | FastAPI | OpenAPI自動生成、Swagger UI + ReDoc |
| ORM | SQLAlchemy 2.0 | DB切り替えの抽象化層 |
| バリデーション | Pydantic v2 | リクエスト/レスポンス型定義 |
| DB | SQLite | 900MB、読み取り専用（年2回更新） |
| 地図UI | Leaflet.js + OpenStreetMap | レスポンシブ対応 |
| ホスティング | Apache + Let's Encrypt | リバースプロキシ + SSL |
| プロセス管理 | systemd | 自動起動 + クラッシュ復旧 |

## 3. データソース

### 3.1 医療情報ネット（年2回更新: 6月末・12月末）

| ファイル | 種別 | 施設数 | 診療科数 |
|---------|------|--------|---------|
| 01-1/01-2 病院 | hospital | 7,640 | 246,480 |
| 02-1/02-2 診療所 | clinic | 76,988 | 627,630 |
| 03-1/03-2 歯科 | dental | 52,985 | 408,996 |
| 04 助産所 | maternity | 2,097 | — |
| 05 薬局 | pharmacy | 60,354 | — |
| **合計** | | **200,064** | **1,283,106** |

データ基準日: 2025-12-01

### 3.2 国税庁 法人番号（月次更新）

全件CSV（Unicode版）: 5,741,920法人、1.2GB
住所ベースマッチングにより **144,919施設 (72.4%)** に法人番号を紐付け済み。

### 3.3 介護サービス情報公表（将来対応）

Phase 2で対応予定。

## 4. DB設計

### 4.1 ER図

```
prefectures ──┐
              ├── facilities (施設マスタ)
cities ───────┘     ├── 1:N ── specialities (診療科・診療時間)
                    ├── 1:N ── business_hours (営業時間帯)
                    ├── 1:1 ── hospital_beds (病床情報)
                    └── corporate_number → 国税庁法人番号
              
specialty_master (診療科マスタ: 118件)
```

### 4.2 テーブル定義

#### facilities（施設）

| カラム | 型 | 説明 |
|-------|-----|------|
| id | VARCHAR(13) PK | 厚労省ID |
| facility_type | SMALLINT NOT NULL | 1:病院 2:診療所 3:歯科 4:助産所 5:薬局 |
| name | TEXT NOT NULL | 正式名称 |
| name_kana | TEXT | フリガナ |
| name_short | TEXT | 略称 |
| name_en | TEXT | 英語名 |
| prefecture_code | CHAR(2) FK | 都道府県コード |
| city_code | CHAR(3) | 市区町村コード |
| address | TEXT | 所在地 |
| latitude | FLOAT | 緯度 |
| longitude | FLOAT | 経度 |
| website_url | TEXT | HP URL |
| corporate_number | VARCHAR(13) | 法人番号（国税庁マッチング） |
| closed_holiday | BOOLEAN | 祝日休診 |
| closed_other | TEXT | その他休診日 |
| closed_weekly | JSON | 曜日別定休 |
| closed_weeks | JSON | 定期週休診 |
| raw_data | JSON | 種別固有の全カラム（将来拡張用） |
| data_date | DATE | データ基準日 |
| created_at / updated_at | DATETIME | タイムスタンプ |

#### specialities（診療科・診療時間）

| カラム | 型 | 説明 |
|-------|-----|------|
| id | INTEGER PK AUTO | サロゲートキー |
| facility_id | VARCHAR(13) FK | → facilities.id |
| specialty_code | VARCHAR(10) | 診療科コード |
| specialty_name | TEXT NOT NULL | 診療科名 |
| time_slot | VARCHAR(10) | 時間帯番号 |
| schedule | JSON NOT NULL | 曜日別診療時間 |
| reception | JSON | 曜日別受付時間 |

#### hospital_beds / business_hours / prefectures / cities / specialty_master

（変更なし、v0.1.0設計のまま）

### 4.3 インデックス

| テーブル | インデックス | 用途 |
|---------|-------------|------|
| facilities | (latitude, longitude) | 近隣検索 |
| facilities | (prefecture_code, city_code) | 地域絞り込み |
| facilities | (facility_type) | 種別絞り込み |
| facilities | (corporate_number) | 法人番号検索 |
| specialities | (facility_id) | JOIN |
| specialities | (specialty_code) | 診療科検索（コード） |
| specialities | (specialty_name) | 診療科検索（名称） |

### 4.4 診療科検索の最適化

128万行の `LIKE '%keyword%'` を回避するため:
1. `specialty_master` でキーワード→コード一覧を解決（118件なので一瞬）
2. `EXISTS` サブクエリでコード列のインデックスを活用

詳細: [developer_notes/01_specialty_search_optimization.md](developer_notes/01_specialty_search_optimization.md)

## 5. API設計

### 5.1 エンドポイント

| メソッド | パス | 説明 | 実装状況 |
|---------|------|------|---------|
| GET | / | Web UI（地図付き検索） | ✅ |
| GET | /api/v1/facilities | 施設検索 | ✅ |
| GET | /api/v1/facilities/nearby | 近隣検索 | ✅ |
| GET | /api/v1/facilities/{id} | 施設詳細 | ✅ |
| GET | /api/v1/specialities | 診療科マスタ | ✅ |
| GET | /api/v1/prefectures | 都道府県一覧 | ✅ |
| GET | /api/v1/stats | 統計情報 | ✅ |
| GET | /api/v1/health | ヘルスチェック | ✅ |
| GET | /docs | Swagger UI (Playground) | ✅ (FastAPI組込) |
| GET | /redoc | ReDoc (APIリファレンス) | ✅ (FastAPI組込) |
| GET | /openapi.json | OpenAPI仕様 | ✅ (FastAPI組込) |

### 5.2 施設詳細レスポンス

```json
{
  "id": "1321316021489",
  "facility_type": 2,
  "facility_type_name": "診療所",
  "name": "to clinic shibuya",
  "name_kana": "トゥークリニックシブヤ",
  "name_en": "to clinic shibuya",
  "address": "東京都渋谷区桜丘町１－４渋谷サクラステージ...",
  "latitude": 35.657157,
  "longitude": 139.701907,
  "corporate_number": "1010005024060",
  "website_url": "https://toclinic.jp/",
  "closed_weekly": {"mon": true, "tue": false, ...},
  "data_date": "2025-12-01",
  "specialities": [...],
  "beds": null,
  "business_hours": null
}
```

## 6. ディレクトリ構成

```
medical_open_data/
├── api/
│   ├── main.py              # FastAPIアプリ + StaticFiles
│   ├── config.py             # DATABASE_URL等
│   ├── database.py           # SQLAlchemy engine/session
│   ├── models.py             # ORMモデル
│   ├── schemas.py            # Pydanticスキーマ
│   ├── routes/
│   │   └── facilities.py     # 全エンドポイント
│   └── services/
│       ├── search.py         # 検索ロジック（EXISTS最適化）
│       └── geo.py            # haversine/bounding box
├── static/
│   └── index.html            # Web UI（Leaflet.js）
├── scripts/
│   ├── fetch_data.py         # 厚労省データDL
│   ├── import_data.py        # CSV→DB取り込み
│   └── match_corporate.py    # 法人番号マッチング
├── data/
│   ├── raw/                  # 厚労省CSV (.gitignore)
│   ├── houjin/               # 国税庁CSV (.gitignore)
│   └── medical.db            # SQLite DB (.gitignore)
├── docs/
│   ├── DESIGN.md             # この文書
│   ├── VISION.md             # データスペース構想
│   ├── DEPLOY.md             # デプロイメモ
│   ├── LAMBDA_ARCHITECTURE.md
│   └── developer_notes/      # 技術ノート
│       ├── README.md
│       ├── 01_specialty_search_optimization.md
│       └── 02_corporate_number_matching.md
├── requirements.txt
├── .gitignore
└── README.md
```

## 7. フェーズ

### Phase 1（MVP）✅ 完了
- [x] データダウンロードスクリプト
- [x] SQLAlchemyモデル定義
- [x] CSV→DBインポーター（バルクインサート）
- [x] 基本検索API（名称, 都道府県, 種別, 診療科）
- [x] 近隣検索（haversine + bounding box）
- [x] 施設詳細（診療科・時間・病床・営業時間）
- [x] 診療科検索の最適化（EXISTS + コード解決）
- [x] Web UI（Leaflet.js + OpenStreetMap）
- [x] 本番デプロイ（systemd + Apache + SSL）
- [x] 法人番号マッチング（72.4%）

### Phase 2（予定）
- [ ] 全文検索 (FTS5)
- [ ] 「今やってる」検索 (open_now)
- [ ] 介護サービスデータ統合
- [ ] ODS-RAM準拠カタログエンドポイント
- [ ] 法人番号マッチング精度向上（国税庁API連携）

### Phase 3（予定）
- [ ] データ自動更新（cron + fetch_data.py）
- [ ] Lambda + S3 デプロイ
- [ ] キャッシュ層
- [ ] レート制限
