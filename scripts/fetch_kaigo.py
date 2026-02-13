#!/usr/bin/env python3
"""介護サービス情報公表システム オープンデータのダウンロード

35サービス種別のCSVを厚労省サイトからダウンロードし data/raw/kaigo/ に保存する。
URL形式: https://www.mhlw.go.jp/content/12300000/jigyosho_XXX.csv
"""

import sys
import time
import requests
from pathlib import Path

BASE_URL = "https://www.mhlw.go.jp/content/12300000"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "kaigo"

# 35サービス種別コード → ファイル名サフィックス & サービス名
SERVICE_CODES = {
    "110": "訪問介護",
    "120": "訪問入浴介護",
    "130": "訪問看護",
    "140": "訪問リハビリテーション",
    "150": "通所介護",
    "155": "通所リハビリテーション",
    "160": "短期入所生活介護",  # was 福祉用具貸与 in some refs, but design says 通所系
    "170": "福祉用具貸与",
    "210": "短期入所生活介護",
    "220": "短期入所療養介護（老健）",
    "230": "短期入所療養介護（病院等）",
    "320": "特定施設入居者生活介護",
    "331": "定期巡回・随時対応型訪問介護看護",
    "332": "夜間対応型訪問介護",
    "333": "地域密着型通所介護",
    "334": "認知症対応型通所介護",
    "335": "小規模多機能型居宅介護",
    "336": "認知症対応型共同生活介護",
    "337": "地域密着型特定施設入居者生活介護",
    "338": "地域密着型介護老人福祉施設入所者生活介護",
    "361": "看護小規模多機能型居宅介護",
    "410": "特定福祉用具販売",
    "430": "居宅介護支援",
    "510": "介護老人福祉施設",
    "520": "介護老人保健施設",
    "530": "介護療養型医療施設",
    "540": "介護医療院",
    "550": "地域密着型介護老人福祉施設",  # duplicate with 338? check
    "551": "介護予防短期入所生活介護",  # possibly
    "710": "定期巡回・随時対応型訪問介護看護",  # possibly予防版
    "720": "介護予防訪問看護",
    "730": "介護予防通所リハビリテーション",
    "760": "介護予防短期入所療養介護（老健）",
    "770": "介護予防短期入所療養介護（病院等）",
    "780": "介護予防特定施設入居者生活介護",
}


def fetch_all():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = []
    
    for code in sorted(SERVICE_CODES.keys()):
        filename = f"jigyosho_{code}.csv"
        url = f"{BASE_URL}/{filename}"
        dest = RAW_DIR / filename
        
        if dest.exists() and dest.stat().st_size > 100:
            print(f"⏭️  {filename} already exists ({dest.stat().st_size:,} bytes), skipping")
            success += 1
            continue
        
        print(f"⬇️  Downloading {filename} ({SERVICE_CODES[code]})...")
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                print(f"   ⚠️  404 Not Found — skipping")
                failed.append((code, "404"))
                continue
            r.raise_for_status()
            
            with open(dest, "wb") as f:
                f.write(r.content)
            
            print(f"   ✅ {dest.stat().st_size:,} bytes")
            success += 1
            time.sleep(0.5)  # be polite
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed.append((code, str(e)))
    
    print(f"\n📊 結果: {success}件成功, {len(failed)}件失敗")
    if failed:
        print("失敗一覧:")
        for code, reason in failed:
            print(f"  {code}: {reason}")


if __name__ == "__main__":
    fetch_all()
