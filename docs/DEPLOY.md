# デプロイメモ

## ローカル

```bash
git clone git@github.com:goodsun/medical_open_data.git
cd medical_open_data
pip install -r requirements.txt
python scripts/fetch_data.py
python scripts/import_data.py
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## AWS (ECS + Fargate + RDS)

### 構成イメージ

```
ALB (HTTPS)
  └── ECS Fargate (FastAPI コンテナ)
        └── RDS PostgreSQL (データ)
```

### TODO

- [ ] Dockerfile作成（python:3.11-slim ベース、multi-stage）
- [ ] docker-compose.yml（ローカル開発用: app + postgres）
- [ ] ECS タスク定義（CPU: 0.5vCPU, Memory: 1GB で十分なはず）
- [ ] RDS: db.t3.micro（20万件 + 128万件で300MB程度、無料枠に収まる）
- [ ] ALB + Route53 でカスタムドメイン
- [ ] GitHub Actions で CI/CD（push → build → deploy）
- [ ] 環境変数は SSM Parameter Store or Secrets Manager

### データ更新

厚労省の更新は年2回（6月末・12月末）。

- [ ] ECS Scheduled Task or Lambda で `fetch_data.py` + `import_data.py` を定期実行
- [ ] または手動トリガー（半年に1回なので自動化は後回しでもOK）

### コスト見積もり（最小構成）

| リソース | 月額目安 |
|---------|---------|
| ECS Fargate (0.5vCPU, 1GB, 常時稼働) | ~$15 |
| RDS db.t3.micro (無料枠) | $0 (1年目) |
| ALB | ~$18 |
| Route53 | ~$0.50 |
| **合計** | **~$34/月** |

※ リクエスト量次第。軽量なら Lambda + API Gateway の方が安い可能性あり。

### Lambda + API Gateway 案

- Mangum で FastAPI を Lambda にデプロイ
- API Gateway → Lambda → SQLite (EFS) or RDS
- リクエスト少ないうちはこっちの方が安い
- SQLite を EFS に置けば RDS すら不要

### フロントエンド

- S3 + CloudFront で静的ホスティング
- React / Next.js + Leaflet (地図)
- API は同一ドメインから叩く
