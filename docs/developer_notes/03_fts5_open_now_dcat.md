# 03: FTS5全文検索・open_nowフィルタ・DCATカタログ

**日付**: 2026-02-13
**バージョン**: v0.1.3

## 背景

Phase 1 MVPの完成後、実用性とデータスペース接続準備のために3機能を追加。

## 1. FTS5 全文検索

### 課題
従来の `LIKE '%keyword%'` はインデックスが効かず、20万件のフルスキャンになる。

### 解決策
SQLite FTS5 仮想テーブル `facilities_fts` を導入。

**NFKC正規化**: 施設名に全角英数（`Ｃｌｉｎｉｃ`等）が多いため、インデックス構築時にPython `unicodedata.normalize("NFKC")` で正規化。検索クエリも同様に正規化し、全角/半角を問わずマッチ可能に。

**trigramトークナイザ**: 当初 `unicode61` を使用したが日本語の部分一致ができなかった（空白区切りトークン化のため）。`tokenize='trigram'`（SQLite 3.34.0+）に切り替え、3文字のn-gramで日本語部分一致を実現。

**ハイブリッド戦略**: trigramは3文字未満のクエリにマッチしないため（「渋谷」「内科」「薬局」等の2文字ワード）、クエリに3文字未満のtermが含まれる場合は自動的にLIKEにフォールバック。

| クエリ | 方式 | 例 |
|--------|------|----|
| 3文字以上 | FTS5 trigram | 「クリニック」「渋谷区」 |
| 3文字未満含む | LIKE | 「渋谷」「内科」 |
| 複合（全term 3文字以上） | FTS5 AND | 「渋谷区 クリニック」 |

### 構造
- `api/services/fts.py` — FTS5テーブル作成・インデックス構築・検索
- `api/main.py` lifespan — 起動時にFTS5テーブルがなければ自動構築
- contentless FTS（`content=` なし）— facilitiesテーブルとの同期問題を回避

### DB移行時の対応
FTS5はSQLite専用。PostgreSQL移行時は `pg_trgm` や `pgroonga` に差し替え。`fts.py` の `fts_search()` インターフェースを維持すれば `search.py` の変更は不要。

## 2. open_now フィルタ

### 課題
「今やってる病院」は最も頻繁なユースケースだが、診療時間データがJSON形式のためSQL単体でのフィルタが困難。

### 解決策
アプリケーション層でのフィルタ。`Specialty.schedule` JSONを解析し、現在のJST曜日・時刻が `start`〜`end` の範囲内かチェック。

- `api/services/open_now.py` — `is_open_now(schedules)` 純粋関数
- DB非依存（JSON解析のみ）→ どのDBでもそのまま動く
- 複数スロット（午前/午後等）のいずれかにマッチすればTrue

### パフォーマンス考慮
`open_now=true` 時は全候補をeager loadしてからPython側でフィルタ。他の条件（都道府県・診療科等）で十分絞り込まれていれば問題ない。全国全施設に `open_now` だけかけると遅い可能性あり → 将来的にはscheduleの非正規化カラム（`open_mon_am` 等）を検討。

## 3. DCAT カタログ

### 目的
IPA ウラノス・エコシステム・データスペース（ODS）への接続準備。データセットのメタデータを機械可読に公開。

### 仕様
`GET /api/v1/catalog` → DCAT-AP準拠 JSON-LD

W3C Data Catalog Vocabulary (DCAT) に従い、以下を返す：
- データセットタイトル・説明
- ソース（厚労省）
- 更新頻度
- 空間範囲（日本全国）
- 配布先（API URL, OpenAPI仕様）

### 今後
ODS-RAMのカタログ仕様が確定したら、それに準拠する形に拡張。

## 4. Web UI — open_nowトグル・診療時間テーブル

### open_nowチェックボックス
検索パネルに「🕐 診療中」チェックボックスを追加。キーワード検索・近隣検索両方で `open_now=true` パラメータを送信。

### 施設詳細の診療時間テーブル
従来はテキストの羅列だった診療科・診療時間を、行=診療科、列=月〜日の表組に変更。

**slot統合の課題**: 厚労省データは同一診療科に最大3スロット（午前/午後/夜間等）を持つ。初期実装でslot1のみ取得した結果、午後のみの診療科が消えるバグがあった。全slotの時間帯を曜日ごとに統合し、開始時刻順にソートして複数行表示（例: `8:30-12:00` / `13:00-17:00`）。

## 5. FTS5 インデックス自動再構築

`api/main.py` の lifespan で、起動時に `facilities_fts` と `facilities` テーブルの件数を比較。不一致があればインデックスを自動再構築。データ更新後の `systemctl restart mods-api` だけでFTSも最新化される。

## 6. レスポンスキャッシュ

読み取り専用のマスタデータ（都道府県一覧・診療科マスタ・統計情報）にTTL付きインメモリキャッシュ（1時間）を導入。`api/routes/facilities.py` の `_cached()` ヘルパー。

データ更新は半年に1回のため、1時間TTLで問題ない。サービス再起動でキャッシュはクリアされる。

## 7. Smoke Test

`tests/test_smoke.py` — 18本のpytestで全エンドポイントの正常動作を確認。

- Health/Stats/Prefectures/Specialities/Catalog/OpenAPI
- 施設検索（キーワード・診療科・種別・都道府県・open_now・ページング）
- 近隣検索（基本・open_now・診療科フィルタ）
- 施設詳細（正常・404）
