# medical_open_data

厚生労働省オープンデータを活用した医療機関検索API

## 概要

厚労省が公開している医療情報ネット・介護サービス情報公表システムのオープンデータを取得・整形し、検索可能なAPIとして提供する。

## データソース

- [医療情報ネット オープンデータ](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/newpage_43373.html)
  - 病院（施設票 / 診療科・診療時間票）
  - 診療所（施設票 / 診療科・診療時間票）
  - 歯科診療所（施設票 / 診療科・診療時間票）
  - 助産所
  - 薬局
- [介護サービス情報公表 オープンデータ](https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html)

## クイックスタート

```bash
# 依存インストール
pip install -r requirements.txt

# データダウンロード（厚労省から最新CSV取得）
python scripts/fetch_data.py

# DBインポート（SQLiteに全データ取り込み、約10分）
python scripts/import_data.py

# APIサーバー起動
uvicorn api.main:app --host 0.0.0.0 --port 8000

# ブラウザで http://localhost:8000/docs を開くとSwagger UIが使える
```

### APIの使い方

```bash
# 渋谷駅から1km以内の内科を検索
curl "http://localhost:8000/api/v1/facilities/nearby?lat=35.658&lng=139.702&radius=1&specialty=内科"

# 東京都の病院一覧
curl "http://localhost:8000/api/v1/facilities?prefecture=13&type=1"

# 施設詳細（診療科・病床情報付き）
curl "http://localhost:8000/api/v1/facilities/0111010000010"

# 統計情報
curl "http://localhost:8000/api/v1/stats"
```

### DB切り替え

環境変数 `DATABASE_URL` を変えるだけ:

```bash
# SQLite（デフォルト）
DATABASE_URL=sqlite:///data/medical.db

# PostgreSQL
DATABASE_URL=postgresql://user:pass@host:5432/medical

# MySQL
DATABASE_URL=mysql+pymysql://user:pass@host:3306/medical
```

## 構成

```
data/
  raw/          # 厚労省からダウンロードしたZIP/CSV
  processed/    # パース・正規化済みデータ
db/             # DB定義・マイグレーション
api/            # REST APIサーバー
scripts/        # データ取得・更新スクリプト
docs/           # 設計ドキュメント
```

## データ更新頻度

厚労省の更新: 年2回（6月末・12月末時点）

## ライセンス

データ: [厚生労働省 利用規約](https://www.mhlw.go.jp/chosakuken/index.html)に準拠  
コード: MIT
