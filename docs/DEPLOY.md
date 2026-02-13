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

## 推奨構成: Lambda + S3 + API Gateway（月額~$1）

詳細は [LAMBDA_ARCHITECTURE.md](./LAMBDA_ARCHITECTURE.md) を参照。

読み取り専用 + 年2回更新 + 300MB = サーバーレスの教科書的ユースケース。

```
Route53 (カスタムドメイン)
  └── API Gateway (HTTP API)
        └── Lambda (FastAPI via Mangum)
              └── /tmp ← S3 から SQLite を DL（コールドスタート時のみ）
```

### TODO

- [ ] `api/lambda_handler.py` 追加（Mangumラッパー）
- [ ] DB最適化（raw_data削除、VACUUM → gzip 100MB以下）
- [ ] SAM or CDK テンプレート作成
- [ ] GitHub Actions で CI/CD（CSV取得 → DB生成 → S3 → Lambda デプロイ）
- [ ] Route53 でカスタムドメイン

### データ更新

厚労省の更新は年2回（6月末・12月末）。

- GitHub Actions で手動 or スケジュールトリガー
- 新SQLiteをS3にアップロード → Lambda は次のコールドスタートで自動切り替え
- ダウンタイムなし

## 代替: ECS + Fargate + RDS（月額~$34）

大量リクエストやコールドスタートが許容できない場合。

| リソース | 月額目安 |
|---------|---------|
| ECS Fargate (0.5vCPU, 1GB) | ~$15 |
| RDS db.t3.micro | $0 (無料枠) → $13 |
| ALB | ~$18 |
| **合計** | **~$34/月** |

## フロントエンド

- S3 + CloudFront で静的ホスティング
- React / Next.js + Leaflet (地図)
- API は同一ドメインから叩く
