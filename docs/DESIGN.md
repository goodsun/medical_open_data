# 設計書 — medical_open_data

## 1. 概要

厚労省オープンデータ（医療情報ネット + 介護サービス情報公表）をDB化し、REST APIで検索可能にする。

## 2. 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| API | FastAPI | async対応、OpenAPI自動生成 |
| ORM | SQLAlchemy 2.0 | DB切り替えの抽象化層 |
| マイグレーション | Alembic | スキーマ変更管理 |
| バリデーション | Pydantic v2 | リクエスト/レスポンス型定義 |
| DB (dev) | SQLite | ローカル開発・テスト |
| DB (prod) | PostgreSQL / MySQL / RDS | 接続文字列の切り替えのみ |

## 3. データソース

### 3.1 医療情報ネット（年2回更新: 6月末・12月末）

| ファイル | 種別 | レコード数 | カラム数 |
|---------|------|-----------|---------|
| 01-1 病院（施設票） | hospital | 7,640 | 65 |
| 01-2 病院（診療科・診療時間） | hospital | 246,480 | 36 |
| 02-1 診療所（施設票） | clinic | 76,988 | 62 |
| 02-2 診療所（診療科・診療時間） | clinic | 627,630 | 36 |
| 03-1 歯科診療所（施設票） | dental | 52,985 | 57 |
| 03-2 歯科診療所（診療科・診療時間） | dental | 408,996 | 36 |
| 04 助産所 | maternity | 2,097 | 153 |
| 05 薬局 | pharmacy | 60,354 | 128 |
| **合計** | | **200,064施設 / 1,283,106診療科** | |

### 3.2 介護サービス情報公表（将来対応）

CSV形式、年2回更新。Phase 2で対応予定。

## 4. DB設計

### 4.1 ER図

```
facilities (施設マスタ)
  ├── 1:N ── specialities (診療科・診療時間)
  ├── 1:N ── business_hours (営業時間帯) ※助産所・薬局用
  ├── 1:1 ── hospital_beds (病床情報) ※病院・診療所のみ
  └── 1:1 ── closed_weeks (定期週休診) ※JSON格納
```

### 4.2 テーブル定義

#### facilities（施設）

全種別を1テーブルに統合。共通カラムのみ正規化、種別固有項目はリレーションで持つ。

| カラム | 型 | 説明 |
|-------|-----|------|
| id | VARCHAR(13) PK | 厚労省ID（例: 0111010000010） |
| facility_type | SMALLINT NOT NULL | 1:病院 2:診療所 3:歯科 4:助産所 5:薬局 |
| name | TEXT NOT NULL | 正式名称 |
| name_kana | TEXT | フリガナ |
| name_short | TEXT | 略称 |
| name_en | TEXT | 英語名 / ローマ字 |
| prefecture_code | CHAR(2) NOT NULL | 都道府県コード (01-47) |
| city_code | CHAR(3) NOT NULL | 市区町村コード |
| address | TEXT | 所在地 |
| latitude | FLOAT | 緯度 |
| longitude | FLOAT | 経度 |
| website_url | TEXT | HP URL |
| closed_holiday | BOOLEAN | 祝日休診 |
| closed_other | TEXT | その他休診日（GW、お盆等） |
| closed_weekly | JSON | 曜日別定休 {"mon":true,...} |
| closed_weeks | JSON | 定期週休診 {"week1":{"mon":true,...},...} |
| raw_data | JSON | 種別固有の全カラム（将来拡張用） |
| data_date | DATE | データ基準日（例: 2025-12-01） |
| created_at | DATETIME | レコード作成日時 |
| updated_at | DATETIME | レコード更新日時 |

#### specialities（診療科・診療時間）

病院・診療所・歯科のみ。IDで施設に紐付く。

| カラム | 型 | 説明 |
|-------|-----|------|
| id | INTEGER PK AUTO | サロゲートキー |
| facility_id | VARCHAR(13) FK | → facilities.id |
| specialty_code | VARCHAR(10) | 診療科目コード |
| specialty_name | TEXT NOT NULL | 診療科目名（例: 内科、小児科） |
| time_slot | VARCHAR(10) | 診療時間帯（午前/午後等） |
| schedule | JSON NOT NULL | 曜日別の時間 (後述) |
| reception | JSON | 曜日別の受付時間 |

`schedule` / `reception` のJSON構造:
```json
{
  "mon": {"start": "09:00", "end": "12:00"},
  "tue": {"start": "09:00", "end": "12:00"},
  "wed": null,
  ...
  "hol": null
}
```

#### hospital_beds（病床情報）

病院・診療所のみ。

| カラム | 型 | 説明 |
|-------|-----|------|
| facility_id | VARCHAR(13) PK FK | → facilities.id |
| general | INTEGER | 一般病床 |
| recuperation | INTEGER | 療養病床 |
| recuperation_medical | INTEGER | 療養（医療保険） |
| recuperation_nursing | INTEGER | 療養（介護保険） |
| psychiatric | INTEGER | 精神病床 |
| tuberculosis | INTEGER | 結核病床 |
| infectious | INTEGER | 感染症病床 |
| total | INTEGER | 合計 |

#### business_hours（営業時間帯）

助産所・薬局用。時間帯が最大4スロットあるため行持ち。

| カラム | 型 | 説明 |
|-------|-----|------|
| id | INTEGER PK AUTO | サロゲートキー |
| facility_id | VARCHAR(13) FK | → facilities.id |
| slot_number | SMALLINT | 時間帯番号 (1-4) |
| hour_type | VARCHAR(20) | "business" / "reception" |
| schedule | JSON NOT NULL | 曜日別の開始/終了時間 |

#### prefectures（都道府県マスタ）

| カラム | 型 | 説明 |
|-------|-----|------|
| code | CHAR(2) PK | 都道府県コード (01-47) |
| name | VARCHAR(4) NOT NULL | 名称（例: 北海道、東京都） |

47件。初期データとしてシードする。

#### cities（市区町村マスタ）

| カラム | 型 | 説明 |
|-------|-----|------|
| prefecture_code | CHAR(2) FK | → prefectures.code |
| code | CHAR(3) NOT NULL | 市区町村コード |
| name | TEXT NOT NULL | 名称（例: 千代田区、札幌市中央区） |
| PK | | (prefecture_code, code) |

約1,870件。総務省の全国地方公共団体コードまたはデータから抽出。

#### specialty_master（診療科マスタ）

| カラム | 型 | 説明 |
|-------|-----|------|
| code | VARCHAR(10) PK | 診療科コード（例: 01001） |
| name | TEXT NOT NULL | 正式名称（例: 内科） |
| category | VARCHAR(50) | 大分類（内科系/外科系/小児科系/...） |

**注意**: 厚労省データの診療科コードはXX991が「その他」の自由記述枠。
同一コード(01991等)に1,000種以上の自由テキストが存在する。

設計方針:
- `specialty_master`には正規コード（01001〜09011等）のみ登録（約100件）
- `specialities.specialty_name`は元データのまま保持（自由記述含む）
- 検索時は正規コードでの完全一致 + 名称の部分一致の両方をサポート
- 将来的に自由記述を正規コードにマッピングする辞書テーブル追加を検討

### 4.3 薬局・助産所の固有データ

**薬局（128カラム）**: 営業時間帯（4スロット×8曜日×開始/終了=64カラム）が大半。
施設固有の属性カラムは実質ゼロ（名称・住所・営業情報のみ）。
→ `facilities`テーブル + `business_hours`テーブルで十分カバー。

**助産所（153カラム）**: 就業時間帯3スロット + 外来受付時間帯3スロット（各8曜日×開始/終了）。
こちらも施設固有属性は少ない。
→ 同様に`business_hours`テーブルで`hour_type`を分けて格納。

`raw_data` JSON列は将来のカラム追加に備えた保険として維持する。

### 4.4 インデックス

| テーブル | インデックス | 用途 |
|---------|-------------|------|
| facilities | (latitude, longitude) | 位置検索 |
| facilities | (prefecture_code) | 都道府県絞り込み |
| facilities | (facility_type) | 種別絞り込み |
| facilities | (name) | 名称検索 |
| specialities | (facility_id) | JOIN |
| specialities | (specialty_name) | 診療科検索 |
| hospital_beds | (facility_id) | JOIN |

全文検索: SQLite → FTS5、PostgreSQL → pg_trgm / GIN

### 4.4 位置検索の実装

**SQLite:**
```python
# Python UDFでhaversine計算
def haversine(lat1, lng1, lat2, lng2):
    ...
    return distance_km

# WHERE distance < radius ORDER BY distance
```

**PostgreSQL (PostGIS):**
```sql
SELECT * FROM facilities
WHERE ST_DWithin(
  ST_MakePoint(longitude, latitude)::geography,
  ST_MakePoint(:lng, :lat)::geography,
  :radius_meters
)
```

→ リポジトリ層で分岐するヘルパーを用意

## 5. API設計

### 5.1 エンドポイント

```
GET /api/v1/facilities          # 施設一覧・検索
GET /api/v1/facilities/{id}     # 施設詳細
GET /api/v1/facilities/nearby   # 近隣検索
GET /api/v1/specialities        # 診療科マスタ
GET /api/v1/stats               # 統計情報
GET /api/v1/health              # ヘルスチェック
```

### 5.2 検索パラメータ

`GET /api/v1/facilities`

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| q | string | フリーワード（名称・住所） |
| type | int[] | 施設種別 (1-5) |
| prefecture | string | 都道府県コード |
| city | string | 市区町村コード |
| specialty | string | 診療科名 |
| open_on | string | 営業中の曜日+時間 (例: "mon:14:00") |
| page | int | ページ番号 (default: 1) |
| per_page | int | 件数 (default: 20, max: 100) |

`GET /api/v1/facilities/nearby`

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| lat | float | 緯度 (必須) |
| lng | float | 経度 (必須) |
| radius | float | 半径km (default: 5, max: 50) |
| type | int[] | 施設種別 |
| specialty | string | 診療科 |
| open_now | bool | 現在営業中のみ |

### 5.3 レスポンス

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1234,
    "pages": 62
  }
}
```

## 6. ディレクトリ構成

```
medical_open_data/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPIアプリ
│   ├── config.py             # 設定（DATABASE_URL等）
│   ├── models.py             # SQLAlchemyモデル
│   ├── schemas.py            # Pydanticスキーマ
│   ├── routes/
│   │   ├── facilities.py     # 施設エンドポイント
│   │   └── stats.py          # 統計エンドポイント
│   └── services/
│       ├── search.py         # 検索ロジック
│       └── geo.py            # 位置計算（DB分岐）
├── db/
│   ├── alembic/              # マイグレーション
│   └── alembic.ini
├── scripts/
│   ├── fetch_data.py         # データダウンロード
│   └── import_data.py        # CSV→DB取り込み
├── data/
│   ├── raw/                  # DLしたCSV (.gitignore)
│   └── processed/            # 中間データ (.gitignore)
├── docs/
│   └── DESIGN.md             # この文書
├── tests/
├── config.yaml               # アプリ設定
├── requirements.txt
├── .env.example
└── README.md
```

## 7. フェーズ

### Phase 1（MVP）
- [x] データダウンロードスクリプト
- [ ] SQLAlchemyモデル定義
- [ ] CSV→DBインポーター
- [ ] 基本検索API (名称, 都道府県, 種別, 診療科)
- [ ] 位置検索 (nearby)

### Phase 2
- [ ] 全文検索 (FTS)
- [ ] 「今やってる」検索 (open_now)
- [ ] 介護サービスデータ統合
- [ ] PostgreSQL対応確認

### Phase 3
- [ ] フロントエンド (地図UI)
- [ ] データ自動更新 (cron)
- [ ] キャッシュ層
- [ ] レート制限

## 8. 環境変数

```bash
# .env
DATABASE_URL=sqlite:///data/medical.db   # dev
# DATABASE_URL=postgresql://user:pass@host:5432/medical  # prod
# DATABASE_URL=mysql+pymysql://user:pass@host:3306/medical  # MySQL
API_HOST=0.0.0.0
API_PORT=8000
DATA_DATE=20251201
```
