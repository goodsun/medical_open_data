#!/usr/bin/env python3
"""介護CSVをkaigo.dbにインポート（FTS5構築込み）"""

import csv
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "kaigo"
DB_PATH = Path(__file__).parent.parent / "data" / "kaigo.db"

# 曜日パースマップ
DAY_MAP = {
    "平日": ["mon", "tue", "wed", "thu", "fri"],
    "月曜日": ["mon"], "火曜日": ["tue"], "水曜日": ["wed"],
    "木曜日": ["thu"], "金曜日": ["fri"], "土曜日": ["sat"],
    "日曜日": ["sun"], "祝日": ["holiday"],
}

# サービス種別マスタ（カテゴリ付き）
SERVICE_CATEGORIES = {
    "110": ("訪問介護", "訪問系"),
    "120": ("訪問入浴介護", "訪問系"),
    "130": ("訪問看護", "訪問系"),
    "140": ("訪問リハビリテーション", "訪問系"),
    "150": ("通所介護", "通所系"),
    "155": ("通所リハビリテーション", "通所系"),
    "160": ("短期入所生活介護", "短期入所系"),
    "170": ("福祉用具貸与", "福祉用具"),
    "210": ("短期入所生活介護", "短期入所系"),
    "220": ("短期入所療養介護（老健）", "短期入所系"),
    "230": ("短期入所療養介護（病院等）", "短期入所系"),
    "320": ("特定施設入居者生活介護", "居住系"),
    "331": ("定期巡回・随時対応型訪問介護看護", "地域密着型"),
    "332": ("夜間対応型訪問介護", "地域密着型"),
    "333": ("地域密着型通所介護", "地域密着型"),
    "334": ("認知症対応型通所介護", "地域密着型"),
    "335": ("小規模多機能型居宅介護", "複合・小規模"),
    "336": ("認知症対応型共同生活介護", "居住系"),
    "337": ("地域密着型特定施設入居者生活介護", "地域密着型"),
    "338": ("地域密着型介護老人福祉施設入所者生活介護", "地域密着型"),
    "361": ("看護小規模多機能型居宅介護", "複合・小規模"),
    "410": ("特定福祉用具販売", "福祉用具"),
    "430": ("居宅介護支援", "居宅支援"),
    "510": ("介護老人福祉施設", "入所系"),
    "520": ("介護老人保健施設", "入所系"),
    "530": ("介護療養型医療施設", "入所系"),
    "540": ("介護医療院", "入所系"),
    "550": ("地域密着型介護老人福祉施設", "入所系"),
    "551": ("介護予防短期入所生活介護", "短期入所系"),
    "710": ("介護予防訪問入浴介護", "訪問系"),
    "720": ("介護予防訪問看護", "訪問系"),
    "730": ("介護予防通所リハビリテーション", "通所系"),
    "760": ("介護予防短期入所療養介護（老健）", "短期入所系"),
    "770": ("介護予防短期入所療養介護（病院等）", "短期入所系"),
    "780": ("介護予防特定施設入居者生活介護", "居住系"),
}


def parse_available_days(raw: str) -> str:
    """利用可能曜日文字列→JSON"""
    result = {d: False for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "holiday"]}
    if not raw:
        return json.dumps(result, ensure_ascii=False)
    for part in raw.split(","):
        part = part.strip()
        for key in DAY_MAP.get(part, []):
            result[key] = True
    return json.dumps(result, ensure_ascii=False)


def safe_float(v):
    if not v or not v.strip():
        return None
    try:
        f = float(v.strip())
        return f if f != 0.0 else None
    except ValueError:
        return None


def safe_int(v):
    if not v or not v.strip():
        return None
    try:
        return int(v.strip())
    except ValueError:
        return None


def create_tables(conn):
    """テーブル作成"""
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS kaigo_service_master (
            code     TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS kaigo_facilities (
            id                    TEXT NOT NULL,
            service_code          TEXT NOT NULL,
            service_type          TEXT NOT NULL,
            name                  TEXT NOT NULL,
            name_kana             TEXT,
            prefecture_code       TEXT NOT NULL,
            city_code             TEXT NOT NULL,
            prefecture_name       TEXT,
            city_name             TEXT,
            address               TEXT,
            address_detail        TEXT,
            latitude              REAL,
            longitude             REAL,
            phone                 TEXT,
            fax                   TEXT,
            corporate_number      TEXT,
            corporate_name        TEXT,
            available_days        TEXT,
            available_days_note   TEXT,
            capacity              INTEGER,
            website_url           TEXT,
            shared_service        TEXT,
            nursing_care_standard TEXT,
            welfare_standard      TEXT,
            note                  TEXT,
            data_date             TEXT,
            created_at            TEXT,
            updated_at            TEXT,
            PRIMARY KEY (id, service_code)
        );

        CREATE INDEX IF NOT EXISTS idx_kaigo_service_code ON kaigo_facilities(service_code);
        CREATE INDEX IF NOT EXISTS idx_kaigo_service_type ON kaigo_facilities(service_type);
        CREATE INDEX IF NOT EXISTS idx_kaigo_pref_city ON kaigo_facilities(prefecture_code, city_code);
        CREATE INDEX IF NOT EXISTS idx_kaigo_latlng ON kaigo_facilities(latitude, longitude);
        CREATE INDEX IF NOT EXISTS idx_kaigo_corporate ON kaigo_facilities(corporate_number);
    """)


def create_fts(conn):
    """FTS5テーブル作成・構築"""
    conn.execute("DROP TABLE IF EXISTS kaigo_facilities_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE kaigo_facilities_fts USING fts5(
            facility_id,
            name,
            name_kana,
            address,
            tokenize='trigram'
        )
    """)
    # 各(id, service_code)ペアに対して1行のFTSエントリを作成
    # facility_id = "id:service_code" で複合キーを表現
    conn.execute("""
        INSERT INTO kaigo_facilities_fts(facility_id, name, name_kana, address)
        SELECT id || ':' || service_code,
               name,
               COALESCE(name_kana, ''),
               COALESCE(address, '')
        FROM kaigo_facilities
    """)
    conn.commit()
    count = conn.execute("SELECT count(*) FROM kaigo_facilities_fts").fetchone()[0]
    return count


def import_service_master(conn):
    """サービス種別マスタ挿入"""
    print("🏷️  サービス種別マスタ...")
    for code, (name, category) in SERVICE_CATEGORIES.items():
        conn.execute(
            "INSERT OR REPLACE INTO kaigo_service_master(code, name, category) VALUES(?, ?, ?)",
            (code, name, category)
        )
    conn.commit()
    print(f"   {len(SERVICE_CATEGORIES)}件")


def import_csv_file(conn, filepath, service_code):
    """1つのCSVファイルをインポート"""
    if not filepath.exists():
        return 0

    now = datetime.utcnow().isoformat()
    count = 0
    batch = []
    BATCH_SIZE = 5000

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header

        for row in reader:
            if len(row) < 16:
                continue

            # 都道府県コード又は市町村コード (6桁) → 2桁 + 4桁
            area_code = row[0].strip()
            prefecture_code = area_code[:2] if len(area_code) >= 2 else area_code
            city_code = area_code[2:] if len(area_code) > 2 else ""

            facility_id = row[15].strip() or row[1].strip()  # 事業所番号 or No
            if not facility_id:
                continue

            # CSVからサービスの種類を取得（実際のデータを優先）
            service_type_from_csv = row[6].strip() if len(row) > 6 else ""
            # マスタにCSVの実名称を反映
            service_type = service_type_from_csv or SERVICE_CATEGORIES.get(service_code, ("不明",))[0]

            batch.append((
                facility_id,
                service_code,
                service_type,
                row[4].strip(),  # name
                row[5].strip() or None,  # name_kana
                prefecture_code,
                city_code,
                row[2].strip() or None,  # prefecture_name
                row[3].strip() or None,  # city_name
                row[7].strip() or None,  # address
                row[8].strip() or None if len(row) > 8 else None,  # address_detail
                safe_float(row[9]) if len(row) > 9 else None,  # latitude
                safe_float(row[10]) if len(row) > 10 else None,  # longitude
                row[11].strip() or None if len(row) > 11 else None,  # phone
                row[12].strip() or None if len(row) > 12 else None,  # fax
                row[13].strip() or None if len(row) > 13 else None,  # corporate_number
                row[14].strip() or None if len(row) > 14 else None,  # corporate_name
                parse_available_days(row[16].strip() if len(row) > 16 else ""),
                row[17].strip() or None if len(row) > 17 else None,  # available_days_note
                safe_int(row[18]) if len(row) > 18 else None,  # capacity
                row[19].strip() or None if len(row) > 19 else None,  # website_url
                row[20].strip() or None if len(row) > 20 else None,  # shared_service
                row[21].strip() or None if len(row) > 21 else None,  # nursing_care_standard
                row[22].strip() or None if len(row) > 22 else None,  # welfare_standard
                row[23].strip() or None if len(row) > 23 else None,  # note
                None,  # data_date
                now,
                now,
            ))
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany("""
                    INSERT OR REPLACE INTO kaigo_facilities VALUES(
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, batch)
                conn.commit()
                batch = []

    if batch:
        conn.executemany("""
            INSERT OR REPLACE INTO kaigo_facilities VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """, batch)
        conn.commit()

    return count


def main():
    print(f"🗄️  DB: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))

    print("📋 テーブル作成...")
    create_tables(conn)

    import_service_master(conn)

    # 全CSVをインポート
    total = 0
    csv_files = sorted(RAW_DIR.glob("jigyosho_*.csv"))
    print(f"\n📂 {len(csv_files)}個のCSVファイルを処理...")

    for filepath in csv_files:
        # ファイル名からサービスコードを抽出
        code = filepath.stem.replace("jigyosho_", "")
        service_name = SERVICE_CATEGORIES.get(code, ("不明",))[0]
        n = import_csv_file(conn, filepath, code)
        if n > 0:
            print(f"   {code} {service_name}: {n:,}件")
        total += n

    print(f"\n✅ 合計 {total:,}件インポート")

    # FTS5構築
    print("\n🔍 FTS5インデックス構築...")
    fts_count = create_fts(conn)
    print(f"   ✅ {fts_count:,}件インデックス化")

    # 統計
    print("\n📊 統計:")
    for row in conn.execute("""
        SELECT service_code, service_type, count(*) as cnt
        FROM kaigo_facilities
        GROUP BY service_code, service_type
        ORDER BY cnt DESC
    """).fetchall():
        print(f"   {row[0]} {row[1]}: {row[2]:,}件")

    total_final = conn.execute("SELECT count(*) FROM kaigo_facilities").fetchone()[0]
    unique_facilities = conn.execute("SELECT count(DISTINCT id) FROM kaigo_facilities").fetchone()[0]
    print(f"\n   総レコード数: {total_final:,}")
    print(f"   ユニーク事業所数: {unique_facilities:,}")

    conn.close()
    print("\n🎉 完了!")


if __name__ == "__main__":
    main()
