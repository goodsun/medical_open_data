# 🏥 MODS — Medical Open Data Search

厚生労働省オープンデータを活用した全国20万件の医療施設検索API + Web UI

**🔗 https://mods.bon-soleil.com/**

## 特徴

- 🔍 **全国200,064施設**を検索（病院・診療所・歯科・助産所・薬局）
- 🗺️ **地図UI** — 現在地から近くの病院を地図で探せる
- 📊 **128万件の診療科データ** — 診療時間・休診日まで
- 🏢 **法人番号紐付き** — 14.5万施設 (72.4%) に国税庁法人番号をマッチング
- 📖 **OpenAPI仕様** — Swagger UI / ReDoc / JSON

## デモ

```bash
# 渋谷駅から1km以内の内科
curl "https://mods.bon-soleil.com/api/v1/facilities/nearby?lat=35.658&lng=139.702&radius=1&specialty=内科"

# 東京都の病院一覧
curl "https://mods.bon-soleil.com/api/v1/facilities?prefecture=13&type=1"

# 施設詳細（法人番号・診療科・病床付き）
curl "https://mods.bon-soleil.com/api/v1/facilities/0111010000010"
```

## クイックスタート（ローカル）

```bash
pip install -r requirements.txt

# 厚労省からCSVダウンロード
python scripts/fetch_data.py

# DBインポート（SQLite、約10分）
python scripts/import_data.py

# 法人番号マッチング（国税庁CSV別途DL要）
python scripts/match_corporate.py

# サーバー起動
uvicorn api.main:app --port 8000
# → http://localhost:8000/ で Web UI
# → http://localhost:8000/docs で API Playground
```

## API エンドポイント

| パス | 説明 |
|------|------|
| `GET /` | Web UI（地図付き検索） |
| `GET /api/v1/facilities` | 施設検索（キーワード・診療科・種別・地域） |
| `GET /api/v1/facilities/nearby` | 近隣検索（緯度経度 + 半径） |
| `GET /api/v1/facilities/{id}` | 施設詳細 |
| `GET /api/v1/specialities` | 診療科マスタ |
| `GET /api/v1/prefectures` | 都道府県一覧 |
| `GET /api/v1/stats` | 統計情報 |
| `GET /docs` | API Playground (Swagger UI) |
| `GET /redoc` | API リファレンス (ReDoc) |
| `GET /openapi.json` | OpenAPI仕様 (JSON) |

## データソース

| ソース | 件数 | 更新 |
|--------|------|------|
| [厚労省 医療情報ネット](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html) | 200,064施設 / 1,283,106診療科 | 年2回 |
| [国税庁 法人番号](https://www.houjin-bangou.nta.go.jp/download/) | 5,741,920法人 | 月次 |

## 技術スタック

FastAPI / SQLAlchemy 2.0 / Pydantic v2 / SQLite / Leaflet.js / OpenStreetMap

## DB切り替え

```bash
DATABASE_URL=sqlite:///data/medical.db       # デフォルト
DATABASE_URL=postgresql://user:pass@host/db  # PostgreSQL
DATABASE_URL=mysql+pymysql://user:pass@host/db  # MySQL
```

## ドキュメント

- [設計書](docs/DESIGN.md)
- [ビジョン（データスペース構想）](docs/VISION.md)
- [デプロイ](docs/DEPLOY.md)
- [Developer Notes](docs/developer_notes/) — 技術的課題と解決策の記録

## ライセンス

データ: [厚生労働省 利用規約](https://www.mhlw.go.jp/chosakuken/index.html)準拠 / コード: MIT
