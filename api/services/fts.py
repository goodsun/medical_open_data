"""FTS5 全文検索サービス（SQLite専用）

SQLiteのFTS5仮想テーブルを使い、施設名・住所の高速全文検索を提供する。
PostgreSQL等に移行する場合はこのモジュールを差し替えるだけでよい。
"""
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import DATABASE_URL

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """全角英数→半角、半角カナ→全角に正規化"""
    import unicodedata
    return unicodedata.normalize("NFKC", text)

# FTS5はSQLite専用
IS_SQLITE = DATABASE_URL.startswith("sqlite")


def create_fts_table(db: Session) -> bool:
    """FTS5仮想テーブルを作成（存在しなければ）。成功時True"""
    if not IS_SQLITE:
        logger.info("FTS5 skipped: not SQLite")
        return False

    try:
        db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS facilities_fts USING fts5(
                facility_id,
                name,
                name_kana,
                address,
                tokenize='unicode61'
            )
        """))
        db.commit()
        return True
    except Exception as e:
        logger.error(f"FTS5 table creation failed: {e}")
        db.rollback()
        return False


def rebuild_fts_index(db: Session) -> int:
    """FTS5インデックスを全件再構築。挿入件数を返す"""
    if not IS_SQLITE:
        return 0

    db.execute(text("DELETE FROM facilities_fts"))
    # 全件取得してPython側でNFKC正規化（全角英数→半角）してからINSERT
    rows = db.execute(text(
        "SELECT id, name, COALESCE(name_kana, ''), COALESCE(address, '') FROM facilities"
    )).fetchall()
    BATCH = 5000
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        db.execute(
            text("INSERT INTO facilities_fts(facility_id, name, name_kana, address) VALUES(:id, :name, :kana, :addr)"),
            [{"id": r[0], "name": _normalize(r[1]), "kana": _normalize(r[2]), "addr": _normalize(r[3])} for r in batch]
        )
    db.commit()
    count = db.execute(text("SELECT count(*) FROM facilities_fts")).scalar()
    return count


def fts_search(db: Session, query: str, limit: int = 1000) -> list:
    """FTS5で施設IDを検索。facility_idのリストを返す。
    
    FTS5が利用不可の場合は空リストを返す（呼び出し元がLIKEにフォールバック）。
    """
    if not IS_SQLITE:
        return []

    try:
        # FTS5テーブルの存在確認
        exists = db.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='facilities_fts'"
        )).fetchone()
        if not exists:
            return []

        # 全角英数→半角に正規化してからFTS検索
        normalized = _normalize(query)
        terms = normalized.strip().split()
        fts_query = " AND ".join(f'"{t}"' for t in terms if t)
        if not fts_query:
            return []

        rows = db.execute(
            text("SELECT facility_id FROM facilities_fts WHERE facilities_fts MATCH :q LIMIT :lim"),
            {"q": fts_query, "lim": limit}
        ).fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        logger.warning(f"FTS5 search failed, falling back to LIKE: {e}")
        return []
