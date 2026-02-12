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
