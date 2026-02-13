# 介護サービスモジュール設計書

## 1. 概要

厚生労働省「介護サービス情報公表システム」のオープンデータを、既存の医療施設検索API（MODS）に介護モジュールとして追加する。

- **データソース**: https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html
- **更新頻度**: 年2回（6月末・12月末時点）
- **データ規模**: 約22万事業所、35サービス種別、70 CSVファイル（約24MB）
- **DB推定サイズ**: 300〜400 MB（FTSインデックス込み）

## 2. 設計方針

### 2.1 DB分離 + API統合（A案）

| 項目 | 医療 | 介護 |
|------|------|------|
| DB | `data/medical.db` | `data/kaigo.db` |
| テーブル名 | `facilities` | `kaigo_facilities` |
| FTS | `facilities_fts` | `kaigo_facilities_fts` |
| APIプレフィックス | `/api/v1/facilities` | `/api/v1/kaigo` |

**理由:**
- 厚労省がデータを明確に分けている → 原典の構造を尊重
- ETL・更新が独立（片方だけ再ビルド可能）
- 既存の医療側コードに変更不要
- DCAT カタログも別データセットとして記述
- 横断検索はAPIレイヤーで実現

### 2.2 共通モジュール再利用

| モジュール | 再利用方式 |
|-----------|-----------|
| `services/geo.py` | そのまま利用（DB非依存） |
| `services/fts.py` | テーブル名をパラメータ化して汎用化 |
| `services/open_now.py` | 介護版は「利用可能曜日」ベース → 別ロジック |
| `models.py` → Prefecture, City | 共通マスタとして`medical.db`から参照 or 介護DBにも複製 |
| `database.py` | 介護用エンジン追加（`kaigo_engine`） |

## 3. データモデル

### 3.1 元データ（CSV 24列）

```
 1. 都道府県コード又は市町村コード  例: "011011" (6桁: 都道府県2桁+市区町村4桁)
 2. No                              例: "0170101950" (=事業所番号と同一)
 3. 都道府県名                      例: "北海道"
 4. 市区町村名                      例: "札幌市中央区"
 5. 事業所名                        例: "訪問介護事業所　心輪"
 6. 事業所名カナ                    例: "ホウモンカイゴジギョウショ　シンワ"
 7. サービスの種類                  例: "訪問介護"
 8. 住所                            例: "札幌市中央区南14条西1丁目2-22"
 9. 方書（ビル名等）                例: ""
10. 緯度                            例: "43.041920500000000"
11. 経度                            例: "141.356799499999970"
12. 電話番号                        例: "011-522-5250"
13. FAX番号                         例: "011-522-0178"
14. 法人番号                        例: "" or 13桁（充填率: サービスにより99%〜低め）
15. 法人の名称                      例: "大樹　株式会社"
16. 事業所番号                      例: "0170101950" (=Noと同一)
17. 利用可能曜日                    例: "平日,土曜日,日曜日,祝日"
18. 利用可能曜日特記事項            例: ""
19. 定員                            例: "0" or "70"
20. URL                             例: ""
21. 高齢者の方と障害者の方が同時一体的に利用できるサービス  例: ""
22. 介護保険の通常の指定基準を満たしている                  例: ""
23. 障害福祉の通常の指定基準を満たしている                  例: ""
24. 備考                            例: ""
```

### 3.2 テーブル設計

```sql
-- 介護事業所テーブル
CREATE TABLE kaigo_facilities (
    id                  TEXT PRIMARY KEY,   -- 事業所番号 (10桁)
    service_code        TEXT NOT NULL,       -- サービス種別コード (3桁: "110", "120", ...)
    service_type        TEXT NOT NULL,       -- サービスの種類 ("訪問介護", "通所介護", ...)
    name                TEXT NOT NULL,       -- 事業所名
    name_kana           TEXT,                -- 事業所名カナ
    prefecture_code     TEXT NOT NULL,       -- 都道府県コード (2桁)
    city_code           TEXT NOT NULL,       -- 市区町村コード (4桁 or 残り部分)
    address             TEXT,                -- 住所
    address_detail      TEXT,                -- 方書（ビル名等）
    latitude            REAL,                -- 緯度
    longitude           REAL,                -- 経度
    phone               TEXT,                -- 電話番号
    fax                 TEXT,                -- FAX番号
    corporate_number    TEXT,                -- 法人番号 (13桁)
    corporate_name      TEXT,                -- 法人の名称
    available_days      TEXT,                -- 利用可能曜日 (JSON: {"mon":true,...})
    available_days_note TEXT,                -- 利用可能曜日特記事項
    capacity            INTEGER,             -- 定員
    website_url         TEXT,                -- URL
    shared_service      TEXT,                -- 共生型サービス
    nursing_care_standard BOOLEAN,           -- 介護保険基準
    welfare_standard    BOOLEAN,             -- 障害福祉基準
    note                TEXT,                -- 備考
    data_date           DATE,                -- データ基準日
    created_at          DATETIME,
    updated_at          DATETIME
);

-- インデックス
CREATE INDEX idx_kaigo_service_code ON kaigo_facilities(service_code);
CREATE INDEX idx_kaigo_service_type ON kaigo_facilities(service_type);
CREATE INDEX idx_kaigo_pref_city ON kaigo_facilities(prefecture_code, city_code);
CREATE INDEX idx_kaigo_latlng ON kaigo_facilities(latitude, longitude);
CREATE INDEX idx_kaigo_corporate ON kaigo_facilities(corporate_number);

-- FTS5 全文検索
CREATE VIRTUAL TABLE kaigo_facilities_fts USING fts5(
    facility_id,
    name,
    name_kana,
    address,
    tokenize='trigram'
);
```

### 3.3 サービス種別マスタ

```sql
CREATE TABLE kaigo_service_master (
    code     TEXT PRIMARY KEY,   -- "110", "120", ...
    name     TEXT NOT NULL,      -- "訪問介護", "訪問入浴介護", ...
    category TEXT                -- "訪問系", "通所系", "入所系", "居宅支援", "福祉用具", "地域密着型"
);
```

サービスカテゴリ分類:

| カテゴリ | サービス種別コード |
|---------|-------------------|
| 訪問系 | 110, 120, 130, 140, 710 |
| 通所系 | 150, 155, 160, 780 |
| 短期入所系 | 210, 220, 230 |
| 入所系 | 510, 520, 530, 540, 550 |
| 居住系 | 320, 331-337, 361-364 |
| 居宅支援 | 430 |
| 福祉用具 | 170, 410 |
| 複合・小規模 | 551, 720, 730, 760, 770 |

### 3.4 同一事業所の複数サービス

一つの事業所（同一事業所番号）が複数サービスを提供するケースがありうる。
その場合、CSVファイルが異なるため別行として登場する。

**方針**: 複合キー `(id, service_code)` で一意にする。
→ 同一事業所が訪問介護と通所介護を提供する場合、2行になる。

```sql
-- PKを変更
ALTER TABLE kaigo_facilities DROP CONSTRAINT pk;
-- 複合PK
PRIMARY KEY (id, service_code)
```

## 4. API設計

### 4.1 エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/v1/kaigo` | 介護事業所一覧（検索・フィルタ） |
| GET | `/api/v1/kaigo/nearby` | 近隣検索（緯度経度+半径） |
| GET | `/api/v1/kaigo/{facility_id}` | 事業所詳細 |
| GET | `/api/v1/kaigo/services` | サービス種別マスタ一覧 |
| GET | `/api/v1/kaigo/stats` | 統計情報 |

### 4.2 検索パラメータ

```
GET /api/v1/kaigo?q=渋谷&service=通所介護&prefecture=13&page=1&per_page=20
```

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| q | string | フリーワード（名称・住所） |
| service | string | サービス種別名（部分一致）またはコード |
| prefecture | string | 都道府県コード (01-47) |
| city | string | 市区町村コード |
| corporate_number | string | 法人番号で検索 |
| available_day | string | 利用可能曜日 (mon/tue/.../sun/holiday) |
| page | int | ページ番号 |
| per_page | int | 1ページあたり件数 (max 100) |

### 4.3 近隣検索

```
GET /api/v1/kaigo/nearby?lat=35.658&lng=139.702&radius=3&service=通所介護
```

### 4.4 レスポンス例

```json
{
  "data": [
    {
      "id": "0170101950",
      "service_code": "110",
      "service_type": "訪問介護",
      "name": "訪問介護事業所 心輪",
      "prefecture_code": "01",
      "prefecture_name": "北海道",
      "city_code": "1011",
      "address": "札幌市中央区南14条西1丁目2-22",
      "latitude": 43.0419,
      "longitude": 141.3568,
      "phone": "011-522-5250",
      "corporate_name": "大樹 株式会社",
      "capacity": 0,
      "available_days": {"mon":true,"tue":true,"wed":true,"thu":true,"fri":true,"sat":true,"sun":true,"holiday":true},
      "distance_km": null
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 35191,
    "pages": 1760
  }
}
```

### 4.5 横断検索（将来）

医療+介護の横断検索は将来エンドポイントとして追加検討:
```
GET /api/v1/search?lat=35.658&lng=139.702&radius=3
→ 医療施設と介護事業所を統合して距離順で返す
```

## 5. ディレクトリ構成

```
medical_open_data/
├── api/
│   ├── main.py                  # kaigo routerを追加
│   ├── config.py                # KAIGO_DATABASE_URL追加
│   ├── database.py              # kaigo_engine, get_kaigo_db追加
│   ├── models.py                # 既存（医療）変更なし
│   ├── kaigo_models.py          # 介護モデル（KaigoFacility, KaigoServiceMaster）
│   ├── schemas.py               # 既存 変更なし
│   ├── kaigo_schemas.py         # 介護スキーマ
│   ├── routes/
│   │   ├── facilities.py        # 既存 変更なし
│   │   ├── kaigo.py             # 介護エンドポイント
│   │   └── catalog.py           # 介護データセット追加
│   └── services/
│       ├── geo.py               # 共通（変更なし）
│       ├── fts.py               # テーブル名パラメータ化
│       ├── open_now.py          # 既存 変更なし
│       └── kaigo_search.py      # 介護検索サービス
├── scripts/
│   ├── fetch_data.py            # 既存 変更なし
│   ├── import_data.py           # 既存 変更なし
│   ├── fetch_kaigo.py           # 介護CSV一括ダウンロード
│   └── import_kaigo.py          # 介護DBインポート
├── data/
│   ├── medical.db               # 既存
│   ├── kaigo.db                 # 新規
│   └── raw/
│       └── kaigo/               # 介護CSVファイル格納
├── static/                      # Web UI（介護タブ追加）
├── tests/
│   ├── test_smoke.py            # 既存
│   └── test_kaigo.py            # 介護テスト
└── docs/
    └── kaigo_design.md          # この文書
```

## 6. 利用可能曜日のパース

元データ: `"平日,土曜日,日曜日,祝日"` のようなカンマ区切り文字列

パースロジック:
```python
DAY_MAP = {
    "平日": ["mon", "tue", "wed", "thu", "fri"],
    "月曜日": ["mon"], "火曜日": ["tue"], "水曜日": ["wed"],
    "木曜日": ["thu"], "金曜日": ["fri"], "土曜日": ["sat"],
    "日曜日": ["sun"], "祝日": ["holiday"],
}

def parse_available_days(raw: str) -> dict:
    result = {d: False for d in ["mon","tue","wed","thu","fri","sat","sun","holiday"]}
    for part in raw.split(","):
        part = part.strip()
        for key in DAY_MAP.get(part, []):
            result[key] = True
    return result
```

保存形式: JSON `{"mon":true,"tue":true,...,"holiday":true}`

## 7. 都道府県コード・市区町村コードの扱い

介護データの「都道府県コード又は市町村コード」は6桁（例: "011011"）。
- 先頭2桁: 都道府県コード（"01"）
- 残り4桁: 市区町村コード（"1011"）

医療データの都道府県コード（2桁）+ city_code（3桁）とは**桁数が異なる**。
→ 介護側は `prefecture_code` (2桁) + `city_code` (4桁) で正規化して格納。

## 8. 実装優先順位

### Phase 1: データパイプライン
1. `scripts/fetch_kaigo.py` — 35種別CSVのダウンロード
2. `scripts/import_kaigo.py` — kaigo.dbへのインポート + FTS構築
3. 動作確認（件数・データ品質チェック）

### Phase 2: API
4. `api/kaigo_models.py` + `api/kaigo_schemas.py`
5. `api/database.py` に kaigo_engine 追加
6. `api/routes/kaigo.py` — 検索・近隣・詳細エンドポイント
7. `api/routes/catalog.py` に介護データセット追加

### Phase 3: UI
8. Web UI に介護タブ/切り替え追加
9. 地図上で医療（青）・介護（緑）を色分け表示

### Phase 4: 横断検索 + ODS
10. 統合検索エンドポイント
11. DCAT カタログ拡充
12. ウラノス・エコシステム接続検討

## 9. 実現可能性の評価

| 項目 | 評価 | 備考 |
|------|------|------|
| データ取得 | ✅ 容易 | UTF-8 BOM、直リンク、24列固定 |
| データ品質 | ✅ 良好 | 緯度経度・法人番号が元データに含まれる |
| DB容量 | ✅ 問題なし | 推定300-400MB、合計1.4GB |
| 既存への影響 | ✅ なし | DB分離、既存コード変更最小限 |
| 工数 | Phase 1-2: 数時間、Phase 3: 半日、Phase 4: 別途 |
| 難易度 | 低〜中 | 医療側のパターンをほぼそのまま適用可能 |

**結論: 実現可能。医療モジュールのパターンを再利用でき、データ品質も高い。**
