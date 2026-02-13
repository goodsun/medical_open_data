"""法人番号マッチング — 国税庁全件CSVと医療施設をマッチング"""
import csv
import sqlite3
import re
import sys
import os
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "medical.db"
HOUJIN_DIR = DATA_DIR / "houjin"

# ========== 法人名抽出 ==========

CORP_PREFIXES = [
    '特定医療法人社団', '特定医療法人財団', '特定医療法人',
    '社会医療法人', '医療法人社団', '医療法人財団', '医療法人',
    '社会福祉法人', '地方独立行政法人', '独立行政法人',
    '国立大学法人', '学校法人',
    '株式会社', '有限会社', '合同会社', '合資会社',
    '公益社団法人', '公益財団法人', '一般社団法人', '一般財団法人',
    '特定非営利活動法人', '宗教法人',
]


def extract_corp_name(facility_name: str) -> str | None:
    """施設名から法人名を抽出"""
    # 全角スペース/半角スペースで分割
    parts = re.split(r'[\s　]+', facility_name.strip())

    if len(parts) >= 2:
        for prefix in CORP_PREFIXES:
            if parts[0].startswith(prefix):
                return parts[0]

    # スペースなしの場合: 「医療法人社団〇〇会△△病院」→「医療法人社団〇〇会」
    for prefix in CORP_PREFIXES:
        if facility_name.startswith(prefix):
            # prefix以降で「会」「園」「社」等で切る
            rest = facility_name[len(prefix):]
            # 「〇〇会」パターン
            m = re.match(r'(.+?(?:会|園|社|組|舎|団))', rest)
            if m:
                return prefix + m.group(1)
            # 会が無い場合（「医療法人徳洲会」等はprefixに含まれないので）
            # スペースなしで法人名が見つからない
            break

    return None


def normalize(text: str) -> str:
    """正規化: 全角→半角、スペース除去、カタカナ→ひらがな等"""
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', '', text)
    return text.lower()


# ========== 法人番号CSV読み込み ==========

def load_houjin_csv() -> dict:
    """国税庁CSVを読み込み、法人名→(法人番号, 住所)のマッピングを作成"""
    # CSVフォーマット (Unicode版):
    # 1:シーケンス番号, 2:法人番号, 3:処理区分, 4:訂正区分, 5:更新年月日,
    # 6:変更年月日, 7:法人名, 8:法人名ふりがな, 9:法人名英語,
    # 10:都道府県コード(JIS), 11:市区町村コード(JIS), 12:郵便番号,
    # 13:所在地, 14:所在地(英語), ...

    corp_map = {}  # normalized_name -> [(corp_number, address, original_name)]
    addr_map = defaultdict(list)  # normalized_addr_prefix -> [(corp_number, name)]

    csv_files = sorted(HOUJIN_DIR.glob("*.csv"))
    if not csv_files:
        print(f"ERROR: No CSV files found in {HOUJIN_DIR}")
        sys.exit(1)

    total = 0
    for csv_file in csv_files:
        print(f"Reading {csv_file.name}...")
        # Try encodings
        for enc in ['utf-8-sig', 'utf-8', 'cp932']:
            try:
                with open(csv_file, encoding=enc, errors='replace') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) < 13:
                            continue
                        corp_number = row[1]
                        corp_name = row[6]
                        address = row[12] if len(row) > 12 else ""

                        if not corp_number or not corp_name:
                            continue

                        total += 1
                        norm_name = normalize(corp_name)
                        if norm_name not in corp_map:
                            corp_map[norm_name] = []
                        corp_map[norm_name].append((corp_number, address, corp_name))

                        # 住所の先頭30文字でもインデックス
                        if address:
                            addr_key = normalize(address[:30])
                            addr_map[addr_key].append((corp_number, corp_name))

                break  # encoding succeeded
            except UnicodeDecodeError:
                continue

    print(f"Loaded {total} corporations, {len(corp_map)} unique names")
    return corp_map, addr_map


# ========== マッチング ==========

def match_facilities(corp_map, addr_map):
    """医療施設と法人番号をマッチング"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT id, name, address, facility_type FROM facilities")
    facilities = c.fetchall()

    matched = 0
    matched_by_name = 0
    matched_by_addr = 0
    total = len(facilities)
    updates = []

    for fid, fname, faddr, ftype in facilities:
        corp_name = extract_corp_name(fname)
        corp_number = None

        # 1. 法人名で完全一致
        if corp_name:
            norm = normalize(corp_name)
            candidates = corp_map.get(norm, [])
            if len(candidates) == 1:
                corp_number = candidates[0][0]
                matched_by_name += 1
            elif len(candidates) > 1 and faddr:
                # 同名法人が複数→住所で絞り込み
                norm_addr = normalize(faddr)
                for cn, addr, _ in candidates:
                    if addr and normalize(addr[:20]) in norm_addr:
                        corp_number = cn
                        matched_by_name += 1
                        break

        # 2. 住所マッチング（法人名抽出できなかった場合）
        # TODO: Phase 2で実装

        if corp_number:
            matched += 1
            updates.append((corp_number, fid))

    # バッチ更新
    if updates:
        c.executemany("UPDATE facilities SET corporate_number = ? WHERE id = ?", updates)
        conn.commit()

    print(f"\n=== マッチング結果 ===")
    print(f"総施設数: {total:,}")
    print(f"マッチ成功: {matched:,} ({matched/total*100:.1f}%)")
    print(f"  法人名一致: {matched_by_name:,}")
    print(f"  住所補完: {matched_by_addr:,}")
    print(f"未マッチ: {total - matched:,}")

    # 種別ごとの統計
    c.execute("""
        SELECT facility_type,
               COUNT(*) as total,
               COUNT(corporate_number) as matched
        FROM facilities GROUP BY facility_type ORDER BY facility_type
    """)
    type_names = {1: '病院', 2: '診療所', 3: '歯科', 4: '助産所', 5: '薬局'}
    print(f"\n--- 種別ごと ---")
    for ft, tot, mat in c.fetchall():
        print(f"  {type_names.get(ft, ft)}: {mat}/{tot} ({mat/tot*100:.1f}%)")

    conn.close()


if __name__ == "__main__":
    print("=== 法人番号マッチング ===")
    print(f"DB: {DB_PATH}")
    print(f"法人CSV: {HOUJIN_DIR}")
    corp_map, addr_map = load_houjin_csv()
    match_facilities(corp_map, addr_map)
