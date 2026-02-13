#!/usr/bin/env python3
"""厚労省CSVをDBにインポート"""

import csv
import sys
import json
from pathlib import Path
from datetime import date

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import engine, SessionLocal, Base
from api.models import (
    Prefecture, City, SpecialtyMaster,
    Facility, Specialty, HospitalBed, BusinessHour
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# 都道府県マスタ
PREFECTURES = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県", "05": "秋田県",
    "06": "山形県", "07": "福島県", "08": "茨城県", "09": "栃木県", "10": "群馬県",
    "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "15": "新潟県",
    "16": "富山県", "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県", "25": "滋賀県",
    "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県",
    "36": "徳島県", "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県", "45": "宮崎県",
    "46": "鹿児島県", "47": "沖縄県",
}

# 診療科カテゴリ
SPECIALTY_CATEGORIES = {
    "01": "内科系", "02": "外科系", "03": "小児科系", "04": "産婦人科系",
    "05": "眼科・耳鼻科系", "06": "皮膚・泌尿器科系", "07": "精神科系",
    "08": "歯科系", "09": "その他",
}

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "hol"]
DATA_DATE = date(2025, 12, 1)


def safe_int(v):
    """空文字やNoneを安全にintに変換"""
    if not v or v.strip() == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def safe_float(v):
    if not v or v.strip() == "":
        return None
    try:
        f = float(v)
        return f if f != 0.0 else None  # 0.0は未登録扱い
    except ValueError:
        return None


def parse_closed_weekly(row, start_col):
    """曜日別休診フラグをJSON化"""
    days_jp = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    result = {}
    for i, day in enumerate(days_jp):
        val = row[start_col + i].strip() if start_col + i < len(row) else ""
        result[day] = val == "1"
    return result


def parse_closed_weeks(row, start_col):
    """定期週休診フラグをJSON化（5週×7曜日=35カラム）"""
    days_jp = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    result = {}
    for week in range(5):
        week_data = {}
        for i, day in enumerate(days_jp):
            col = start_col + week * 7 + i
            val = row[col].strip() if col < len(row) else ""
            week_data[day] = val == "1"
        if any(week_data.values()):
            result[f"week{week+1}"] = week_data
    return result if result else None


def parse_schedule(row, start_col):
    """曜日別の開始/終了時間ペアをJSON化"""
    schedule = {}
    for i, day in enumerate(DAYS):
        s_col = start_col + i * 2
        e_col = s_col + 1
        start = row[s_col].strip() if s_col < len(row) else ""
        end = row[e_col].strip() if e_col < len(row) else ""
        if start and end:
            schedule[day] = {"start": start, "end": end}
        else:
            schedule[day] = None
    return schedule


def import_prefectures(session):
    """都道府県マスタ"""
    print("📍 都道府県マスタ...")
    for code, name in PREFECTURES.items():
        session.merge(Prefecture(code=code, name=name))
    session.commit()
    print(f"   {len(PREFECTURES)}件")


def import_cities(session):
    """市区町村マスタ（データから抽出）"""
    print("🏘️  市区町村マスタ...")
    cities = {}

    for fname in RAW_DIR.glob("*.csv"):
        with open(fname, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)

            # カラム位置を特定
            pref_idx = None
            city_idx = None
            addr_idx = None
            for i, h in enumerate(header):
                if h == "都道府県コード":
                    pref_idx = i
                elif h == "市区町村コード":
                    city_idx = i
                elif h == "所在地":
                    addr_idx = i

            if pref_idx is None or city_idx is None:
                continue

            for row in reader:
                pcode = row[pref_idx].strip()
                ccode = row[city_idx].strip()
                if pcode and ccode and (pcode, ccode) not in cities:
                    # 住所から市区町村名を推定（都道府県名を除いた先頭部分）
                    addr = row[addr_idx].strip() if addr_idx and addr_idx < len(row) else ""
                    # 都道府県名を除去して市区町村名を抽出
                    pref_name = PREFECTURES.get(pcode, "")
                    city_name = addr.replace(pref_name, "").split("区")[0] + "区" if "区" in addr.replace(pref_name, "") else ""
                    if not city_name:
                        city_name = ccode  # フォールバック
                    cities[(pcode, ccode)] = city_name

    for (pcode, ccode), name in cities.items():
        session.merge(City(prefecture_code=pcode, code=ccode, name=name))
    session.commit()
    print(f"   {len(cities)}件")


def import_facility_file(session, filename, facility_type, bed_start_col=None, bed_cols=None):
    """施設CSVを取り込み"""
    filepath = RAW_DIR / filename
    if not filepath.exists():
        print(f"   ⚠️ {filename} not found, skipping")
        return 0

    count = 0
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            if len(row) < 13:
                continue

            # 薬局はカラム構成が異なる
            if facility_type == 5:
                fac = Facility(
                    id=row[0].strip(),
                    facility_type=facility_type,
                    name=row[1].strip(),
                    name_kana=row[2].strip() or None,
                    name_short=None,
                    name_en=row[3].strip() or None,
                    prefecture_code=row[5].strip(),
                    city_code=row[6].strip(),
                    address=row[7].strip() or None,
                    latitude=safe_float(row[8]),
                    longitude=safe_float(row[9]),
                    website_url=row[10].strip() or None,
                    closed_holiday=row[62].strip() == "1" if len(row) > 62 else None,
                    closed_other=row[63].strip() or None if len(row) > 63 else None,
                    closed_weekly=parse_closed_weekly(row, 19),  # 定期閉店毎週
                    closed_weeks=None,  # 薬局は定期週なし（別形式）
                    data_date=DATA_DATE,
                )
            else:
                fac = Facility(
                    id=row[0].strip(),
                    facility_type=facility_type,
                    name=row[1].strip(),
                    name_kana=row[2].strip() or None,
                    name_short=row[3].strip() or None,
                    name_en=row[5].strip() or None,
                    prefecture_code=row[7].strip(),
                    city_code=row[8].strip(),
                    address=row[9].strip() or None,
                    latitude=safe_float(row[10]),
                    longitude=safe_float(row[11]),
                    website_url=row[12].strip() or None,
                    closed_holiday=row[55].strip() == "1" if len(row) > 55 else None,
                    closed_other=row[56].strip() or None if len(row) > 56 else None,
                    closed_weekly=parse_closed_weekly(row, 13),
                    closed_weeks=parse_closed_weeks(row, 20),
                    data_date=DATA_DATE,
                )

            session.merge(fac)

            # 病床情報（病院・診療所のみ）
            if bed_start_col and bed_cols:
                bed_data = {}
                for i, col_name in enumerate(bed_cols):
                    idx = bed_start_col + i
                    bed_data[col_name] = safe_int(row[idx]) if idx < len(row) else None
                if any(v is not None for v in bed_data.values()):
                    session.merge(HospitalBed(facility_id=row[0].strip(), **bed_data))

            count += 1
            if count % 2000 == 0:
                session.commit()
                print(f"   {count:,}...")

    session.commit()
    return count


def import_speciality_file(session, filename):
    """診療科CSVを取り込み（バルクインサート）"""
    filepath = RAW_DIR / filename
    if not filepath.exists():
        print(f"   ⚠️ {filename} not found, skipping")
        return 0

    count = 0
    batch = []
    BATCH_SIZE = 5000

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # header

        for row in reader:
            if len(row) < 36:
                continue

            schedule = parse_schedule(row, 4)
            reception = parse_schedule(row, 20)

            batch.append({
                "facility_id": row[0].strip(),
                "specialty_code": row[1].strip() or None,
                "specialty_name": row[2].strip(),
                "time_slot": row[3].strip() or None,
                "schedule": json.dumps(schedule, ensure_ascii=False),
                "reception": json.dumps(reception, ensure_ascii=False),
            })
            count += 1

            if len(batch) >= BATCH_SIZE:
                session.execute(Specialty.__table__.insert(), batch)
                session.commit()
                batch = []
                print(f"   {count:,}...")

    if batch:
        session.execute(Specialty.__table__.insert(), batch)
        session.commit()

    return count


def import_specialty_master(session):
    """診療科マスタ（正規コードのみ）"""
    print("🏷️  診療科マスタ...")
    seen = set()

    for fname in ["01-2_hospital_speciality_hours_20251201.csv",
                   "02-2_clinic_speciality_hours_20251201.csv",
                   "03-2_dental_speciality_hours_20251201.csv"]:
        filepath = RAW_DIR / fname
        if not filepath.exists():
            continue
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                code = row[1].strip()
                name = row[2].strip()
                # XX991は「その他」自由記述なのでマスタに入れない
                if code and not code.endswith("991") and code not in seen:
                    cat_key = code[:2]
                    category = SPECIALTY_CATEGORIES.get(cat_key, "その他")
                    session.merge(SpecialtyMaster(code=code, name=name, category=category))
                    seen.add(code)

    session.commit()
    print(f"   {len(seen)}件")


def import_business_hours_pharmacy(session):
    """薬局の営業時間帯を取り込み"""
    filepath = RAW_DIR / "05_pharmacy_20251201.csv"
    if not filepath.exists():
        return 0

    print("🕐 薬局営業時間...")
    count = 0

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)

        for row in reader:
            fac_id = row[0].strip()
            # 4スロット × 開店時間帯 (col 64-127)
            for slot in range(4):
                base = 64 + slot * 16
                schedule = parse_schedule(row, base)
                if any(v is not None for v in schedule.values()):
                    session.add(BusinessHour(
                        facility_id=fac_id,
                        slot_number=slot + 1,
                        hour_type="business",
                        schedule=schedule,
                    ))
                    count += 1

            if count % 10000 == 0 and count > 0:
                session.flush()

    session.commit()
    return count


def import_business_hours_maternity(session):
    """助産所の就業時間・受付時間を取り込み"""
    filepath = RAW_DIR / "04_maternity_home_20251201.csv"
    if not filepath.exists():
        return 0

    print("🕐 助産所営業時間...")
    count = 0

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)

        for row in reader:
            fac_id = row[0].strip()
            # 就業時間帯 3スロット (col 57-104)
            for slot in range(3):
                base = 57 + slot * 16
                schedule = parse_schedule(row, base)
                if any(v is not None for v in schedule.values()):
                    session.add(BusinessHour(
                        facility_id=fac_id,
                        slot_number=slot + 1,
                        hour_type="business",
                        schedule=schedule,
                    ))
                    count += 1

            # 外来受付時間帯 3スロット (col 105-152)
            for slot in range(3):
                base = 105 + slot * 16
                schedule = parse_schedule(row, base)
                if any(v is not None for v in schedule.values()):
                    session.add(BusinessHour(
                        facility_id=fac_id,
                        slot_number=slot + 1,
                        hour_type="reception",
                        schedule=schedule,
                    ))
                    count += 1

    session.commit()
    return count


def main():
    print("🗄️  テーブル作成...")
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # マスタ
        import_prefectures(session)
        import_cities(session)
        import_specialty_master(session)

        # 施設（病院）
        hospital_bed_cols = ["general", "recuperation", "recuperation_medical",
                             "recuperation_nursing", "psychiatric", "tuberculosis",
                             "infectious", "total"]
        print("🏥 病院...")
        n = import_facility_file(session, "01-1_hospital_facility_info_20251201.csv",
                                 facility_type=1, bed_start_col=57, bed_cols=hospital_bed_cols)
        print(f"   ✅ {n:,}件")

        # 施設（診療所）
        clinic_bed_cols = ["general", "recuperation", "recuperation_medical",
                           "recuperation_nursing", "total"]
        print("🏥 診療所...")
        n = import_facility_file(session, "02-1_clinic_facility_info_20251201.csv",
                                 facility_type=2, bed_start_col=57, bed_cols=clinic_bed_cols)
        print(f"   ✅ {n:,}件")

        # 施設（歯科）
        print("🦷 歯科診療所...")
        n = import_facility_file(session, "03-1_dental_facility_info_20251201.csv",
                                 facility_type=3)
        print(f"   ✅ {n:,}件")

        # 施設（助産所）
        print("👶 助産所...")
        n = import_facility_file(session, "04_maternity_home_20251201.csv",
                                 facility_type=4)
        print(f"   ✅ {n:,}件")

        # 施設（薬局）
        print("💊 薬局...")
        n = import_facility_file(session, "05_pharmacy_20251201.csv",
                                 facility_type=5)
        print(f"   ✅ {n:,}件")

        # 診療科
        print("📋 病院 診療科...")
        n = import_speciality_file(session, "01-2_hospital_speciality_hours_20251201.csv")
        print(f"   ✅ {n:,}件")

        print("📋 診療所 診療科...")
        n = import_speciality_file(session, "02-2_clinic_speciality_hours_20251201.csv")
        print(f"   ✅ {n:,}件")

        print("📋 歯科 診療科...")
        n = import_speciality_file(session, "03-2_dental_speciality_hours_20251201.csv")
        print(f"   ✅ {n:,}件")

        # 営業時間
        n = import_business_hours_pharmacy(session)
        print(f"   ✅ 薬局営業時間 {n:,}件")

        n = import_business_hours_maternity(session)
        print(f"   ✅ 助産所営業時間 {n:,}件")

        print("\n🎉 インポート完了!")

    finally:
        session.close()


if __name__ == "__main__":
    main()
