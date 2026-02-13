"""アプリケーション設定"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'medical.db'}"
)

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DATA_DATE = os.getenv("DATA_DATE", "20251201")
