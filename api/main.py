"""FastAPI アプリケーション"""
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes.facilities import router as facilities_router
from .routes.catalog import router as catalog_router
from .database import SessionLocal
from .services.fts import create_fts_table, rebuild_fts_index, IS_SQLITE

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時にFTS5インデックスを確認・構築"""
    if IS_SQLITE:
        db = SessionLocal()
        try:
            from sqlalchemy import text
            exists = db.execute(text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='facilities_fts'"
            )).fetchone()
            if not exists:
                logger.info("FTS5: Creating index...")
                if create_fts_table(db):
                    count = rebuild_fts_index(db)
                    logger.info(f"FTS5: Indexed {count:,} facilities")
            else:
                logger.info("FTS5: Index already exists")
        except Exception as e:
            logger.warning(f"FTS5 init failed (non-fatal): {e}")
        finally:
            db.close()
    yield


app = FastAPI(
    title="Medical Open Data API",
    description="厚生労働省オープンデータを活用した医療施設検索API",
    version="0.1.3",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS（開発用に全許可、本番では制限する）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facilities_router)
app.include_router(catalog_router)


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
