# Developer Note: 診療科検索のパフォーマンス最適化

## 背景

厚労省オープンデータの医療施設検索API（FastAPI + SQLAlchemy + SQLite）を構築中、
`q=渋谷&specialty=内科` のような「フリーワード × 診療科」検索が **30秒以上タイムアウト** する問題に直面した。

### データ規模

| テーブル | レコード数 |
|---|---|
| facilities | 200,064 |
| specialities | 1,283,106 |
| business_hours | 83,386 |

SQLite DBサイズ: **約900MB**

## 問題の経緯

### 第1段階: JOIN + DISTINCT + COUNT が致命的に遅い

最初の実装:

```python
query = db.query(Facility)
query = query.filter(Facility.address.contains('渋谷'))
query = query.join(Facility.specialities).filter(
    Specialty.specialty_name.contains('内科')
).distinct()

total = query.count()  # ← ここで死ぬ
facilities = query.offset(...).limit(...).all()
```

`LIKE '%内科%'` が128万行のspecialitiesテーブルをフルスキャンし、
さらにJOIN → DISTINCT → COUNT の3連コンボでSQLiteが固まる。

**結果: 30秒以上タイムアウト（応答なし）**

直接SQLiteで同等クエリを実行すると0.26秒で返るのに、
SQLAlchemyのORMレイヤーでは桁違いに遅かった。

### 第2段階: サブクエリに分離 → まだ遅い

JOINをやめてサブクエリに分離:

```python
spec_subq = (
    db.query(Specialty.facility_id)
    .filter(Specialty.specialty_name.contains(specialty))
    .distinct()
    .subquery()
)
query = query.filter(Facility.id.in_(db.query(spec_subq.c.facility_id)))
```

**結果: 約11秒** — 改善したが実用には遠い。

`LIKE '%内科%'` が128万行フルスキャンする問題は解消されていない。

### 第3段階: マスタコード解決 + EXISTS = 解決

#### 気づき: specialty_masterテーブルの活用

`specialty_master` テーブルには118件の正規診療科コードがある。
「内科」で検索すると37件のコード（`01001`=内科, `01002`=感染症内科, ...）がヒットする。

このコード一覧でフィルタすれば、**specialty_code列のインデックスが効く**。
`LIKE '%内科%'` の128万行フルスキャンが不要になる。

#### 気づき: EXISTSはSQLiteと相性が良い

IN句にサブクエリを渡すと、SQLiteのクエリプランナーが最適化しにくい。
EXISTSに書き換えると、外側クエリ（facilitiesのフリーワード絞り込み結果）の
各行に対してインデックスを使った存在チェックになる。

```python
def _resolve_specialty_codes(db, keyword):
    """診療科キーワード → コード一覧（マスタは118件なので一瞬）"""
    return [row[0] for row in
        db.query(SpecialtyMaster.code)
        .filter(SpecialtyMaster.name.contains(keyword))
        .all()
    ]

# 検索本体
codes = _resolve_specialty_codes(db, '内科')
exists_q = (
    db.query(Specialty.id)
    .filter(
        Specialty.facility_id == Facility.id,  # 相関サブクエリ
        Specialty.specialty_code.in_(codes),    # インデックス活用
    )
    .exists()
)
query = query.filter(exists_q)
```

**結果: 0.76秒** 🎉

### パフォーマンス推移

| 手法 | 所要時間 | 倍率 |
|---|---|---|
| JOIN + DISTINCT + COUNT | >30秒 (timeout) | - |
| サブクエリ分離 | 11秒 | 3x |
| **EXISTS + コード解決** | **0.76秒** | **40x+** |

## 技術的な教訓

### 1. SQLiteで大テーブルのJOIN + DISTINCT + COUNTは避ける

SQLiteのクエリプランナーはPostgreSQLほど賢くない。
128万行テーブルとのJOINは、サブクエリかEXISTSに分離すべき。

### 2. LIKE '%keyword%' はインデックスが効かない

`specialty_name LIKE '%内科%'` は必ずフルスキャン。
マスタテーブルでキーワード→コードに変換し、コード列（インデックスあり）で検索する。

**マスタテーブルは118件なのでLIKEでも一瞬。大テーブルのLIKEを避けるための中間層。**

### 3. EXISTSはSQLiteの相関サブクエリ最適化と相性が良い

`WHERE EXISTS (SELECT 1 FROM specialities WHERE facility_id = facilities.id AND ...)`

外側のクエリで絞り込まれた行数分だけ、インデックスを使った存在チェックが走る。
「渋谷」で絞り込むと数百件 → 数百回のインデックスルックアップで済む。

### 4. SQLAlchemy ORMのオーバーヘッドに注意

同じクエリでも:
- 生SQLite: 0.26秒
- SQLAlchemy ORM: 0.76秒

ORMのオブジェクトマッピングコストは無視できない。
ただしEXISTS最適化後は実用範囲内なので、ORM/DB切り替えの利便性を優先した。

### 5. 段階的に検証する

「なぜ遅いか」を切り分けるために:
1. まず生SQLで同等クエリを実行 → DB自体の問題か確認
2. SQLAlchemyで `.limit()` のみ（countなし）→ countが原因か確認
3. countを残してクエリ構造を変更 → 最適な構造を探索

## 将来の改善案

- **FTS5 (Full-Text Search)**: SQLiteのFTS5拡張でフリーワード検索を高速化
- **PostgreSQL移行**: 本番規模ではGINインデックス + `pg_trgm` で部分一致が桁違いに速い
- **キャッシュ層**: よく検索される診療科コードのfacility_idリストをRedis等にキャッシュ
- **Materialized View**: 都道府県 × 診療科の組み合わせ別facility_idを事前計算

---

*2026-02-13 — Phase 1 PoC開発中に記録*
*32分でPoC完成、うちパフォーマンス最適化に約15分*
