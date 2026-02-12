#!/usr/bin/env python3
"""厚労省オープンデータのダウンロード"""

import os
import requests
import zipfile
from pathlib import Path

BASE_URL = "https://www.mhlw.go.jp/content/11121000"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# 最新データ (2025年12月版)
DATASETS = {
    "hospital_facility": "01-1_hospital_facility_info_{date}.zip",
    "hospital_speciality": "01-2_hospital_speciality_hours_{date}.zip",
    "clinic_facility": "02-1_clinic_facility_info_{date}.zip",
    "clinic_speciality": "02-2_clinic_speciality_hours_{date}.zip",
    "dental_facility": "03-1_dental_facility_info_{date}.zip",
    "dental_speciality": "03-2_dental_speciality_hours_{date}.zip",
    "maternity": "04_maternity_home_{date}.zip",
    "pharmacy": "05_pharmacy_{date}.zip",
}

DEFAULT_DATE = "20251201"


def fetch_all(date: str = DEFAULT_DATE):
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for name, template in DATASETS.items():
        filename = template.format(date=date)
        url = f"{BASE_URL}/{filename}"
        dest = RAW_DIR / filename

        if dest.exists():
            print(f"⏭️  {filename} already exists, skipping")
            continue

        print(f"⬇️  Downloading {filename}...")
        r = requests.get(url, stream=True)
        r.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"   {dest.stat().st_size:,} bytes")

        # Extract
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(RAW_DIR)
            print(f"   Extracted: {', '.join(zf.namelist())}")

    print("\n✅ All datasets downloaded")


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATE
    fetch_all(date)
