"""DB接続・セッション管理"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DATABASE_URL, KAIGO_DATABASE_URL

# --- 医療DB ---
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI Depends用（医療DB）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 介護DB ---
kaigo_connect_args = {}
if KAIGO_DATABASE_URL.startswith("sqlite"):
    kaigo_connect_args["check_same_thread"] = False

kaigo_engine = create_engine(KAIGO_DATABASE_URL, connect_args=kaigo_connect_args, echo=False)

if KAIGO_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(kaigo_engine, "connect")
    def set_kaigo_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

KaigoSessionLocal = sessionmaker(bind=kaigo_engine, autocommit=False, autoflush=False)


class KaigoBase(DeclarativeBase):
    pass


def get_kaigo_db():
    """FastAPI Depends用（介護DB）"""
    db = KaigoSessionLocal()
    try:
        yield db
    finally:
        db.close()
