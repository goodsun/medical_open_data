# Lambda + SQLite アーキテクチャ

## なぜこれが成立するか

このプロジェクトのデータ特性:

- **読み取り専用** — ユーザーが書き込むデータはない
- **更新頻度が極めて低い** — 年2回（6月末・12月末）
- **データサイズが小さい** — SQLiteで約300MB（JSON列を最適化すればもっと小さい）
- **同時書き込みなし** — SQLiteの最大の弱点が問題にならない

→ **RDBMSのサーバーを常時稼働させる理由がない**

## 構成

```
Route53 (カスタムドメイン)
  └── API Gateway (HTTP API)
        └── Lambda (FastAPI via Mangum)
              └── EFS (SQLite DB ファイル)
```

### 代替: S3 + Lambda Layers

```
API Gateway
  └── Lambda
        └── /tmp に S3 から SQLite を DL（コールドスタート時のみ）
```

- EFSより安い（S3のGET料金のみ）
- コールドスタートで数秒のDLが入るが、ウォームなら不要
- SQLite 300MB → gzip で100MB以下 → Lambda の /tmp (10GB) に余裕で入る

## Mangum（FastAPI → Lambda アダプタ）

```python
# api/lambda_handler.py
from mangum import Mangum
from api.main import app

handler = Mangum(app)
```

たったこれだけで既存のFastAPIコードがLambdaで動く。コード変更ゼロ。

## コスト比較

### ECS Fargate（常時稼働）
| 項目 | 月額 |
|-----|------|
| Fargate (0.5vCPU, 1GB) | ~$15 |
| RDS db.t3.micro | $0 (無料枠) → $13 (2年目〜) |
| ALB | ~$18 |
| **合計** | **$33〜46/月** |

### Lambda + API Gateway + EFS
| 項目 | 月額 |
|-----|------|
| Lambda (100万リクエスト/月) | $0 (無料枠) |
| API Gateway (100万リクエスト) | ~$1 |
| EFS (1GB) | ~$0.30 |
| **合計** | **~$1.30/月** |

### Lambda + API Gateway + S3
| 項目 | 月額 |
|-----|------|
| Lambda | $0 (無料枠) |
| API Gateway | ~$1 |
| S3 (300MB) | ~$0.01 |
| **合計** | **~$1/月** |

**月額$1 vs $34。30倍以上のコスト差。**

## トレードオフ

| | Lambda + SQLite | ECS + RDS |
|---|---|---|
| コスト | ◎ ~$1/月 | △ ~$34/月 |
| コールドスタート | △ 1-3秒 | ◎ 常時レスポンス |
| スケーラビリティ | ○ 自動スケール | ○ 手動/オートスケール |
| 同時接続 | ○ Lambda並列実行 | ○ コネクションプール |
| データ更新 | △ DBファイル差し替え | ◎ マイグレーション |
| 運用負荷 | ◎ ほぼゼロ | △ サーバー管理あり |
| ローカル開発 | ◎ 同じコードがそのまま動く | ◎ 同じ |

## データ更新フロー（Lambda版）

```
1. GitHub Actions (半年に1回 or 手動トリガー)
   └── fetch_data.py → CSVダウンロード
   └── import_data.py → SQLite DB生成
   └── gzip → S3 にアップロード
   └── Lambda 関数を更新（新しいDB参照）

※ ダウンタイムなし（旧DBのLambdaが動いている間に新DBを準備→切り替え）
```

## DB最適化（SQLiteを小さくする）

現在903MBだが最適化の余地あり:

- [ ] `raw_data` JSON列を削除（必要な項目は正規カラムに展開済み）
- [ ] 診療科の `schedule`/`reception` を正規カラム化（JSON→個別カラム）
- [ ] `VACUUM` でフラグメンテーション解消
- [ ] 不要なインデックスの見直し

→ **300MB以下、gzipで100MB以下** が目標

## 実装ステップ

1. [ ] `api/lambda_handler.py` 追加（Mangumラッパー、3行）
2. [ ] DB最適化（raw_data削除、VACUUM）→ サイズ確認
3. [ ] SAM or CDK テンプレート作成
4. [ ] GitHub Actions でビルド → S3 → Lambda デプロイ
5. [ ] カスタムドメイン設定

## まとめ

読み取り専用 + 低頻度更新 + 小データ = **Lambda + SQLite が最適解**。
サーバーレスの教科書的ユースケース。月額$1で全国の医療施設検索APIが動く。
