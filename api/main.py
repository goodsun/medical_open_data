"""FastAPI アプリケーション"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.facilities import router as facilities_router

app = FastAPI(
    title="Medical Open Data API",
    description="厚生労働省オープンデータを活用した医療施設検索API",
    version="0.1.0",
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


@app.get("/")
def root():
    return {
        "name": "Medical Open Data API",
        "version": "0.1.0",
        "docs": "/docs",
        "source": "厚生労働省 医療情報ネット オープンデータ",
    }
