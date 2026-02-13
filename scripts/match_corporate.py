"""法人番号マッチング — 国税庁全件CSVと医療施設をマッチング
戦略:
  Phase 1: 法人名の完全一致マッチ
  Phase 2: 住所ベースマッチ（医療関連法人に絞ってメモリ節約）
"""
import csv
import sqlite3
import re
import sys
import unicodedata
from typing import Optional
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "medical.db"
HOUJIN_DIR = DATA_DIR / "houjin"

CORP_PREFIXES = [
    '特定医療法人社団', '特定医療法人財団', '特定医療法人',
    '社会医療法人', '医療法人社団', '医療法人財団', '医療法人',
    '社会福祉法人', '地方独立行政法人', '独立行政法人',
    '国立大学法人', '学校法人',
    '株式会社', '有限会社', '合同会社', '合資会社',
    '公益社団法人', '公益財団法人', '一般社団法人', '一般財団法人',
    '特定非営利活動法人', '宗教法人',
]

# 住所マッチ対象の法人種別プレフィックス
MEDICAL_CORP_PREFIXES = [
    '医療法人', '社会医療法人', '特定医療法人',
    '社会福祉法人', '独立行政法人', '地方独立行政法人',
    '国立大学法人', '学校法人',
    '一般社団法人', '一般財団法人', '公益社団法人', '公益財団法人',
    '株式会社', '有限会社', '合同会社',  # 薬局は株式会社が多い
    '特定非営利活動法人',
]


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', '', text)
    return text.lower()


def normalize_address(addr: str) -> str:
    """住所を正規化（番地レベルまで）"""
    addr = unicodedata.normalize('NFKC', addr)
    addr = re.sub(r'\s+', '', addr)
    # 「丁目」「番地」「号」の前の数字を半角に（NFKCで済むはず）
    # ビル名・階数を除去（最後の方にある）
    # 簡易: 数字+階、数字+F、ビル名っぽい部分を除去
    addr = re.sub(r'[（(].+?[）)]', '', addr)  # 括弧内除去
    return addr


def addr_key(addr: str, level: int = 3) -> str:
    """住所からマッチング用キーを生成
    level 1: 都道府県+市区町村
    level 2: +町名
    level 3: +番地（デフォルト）
    """
    norm = normalize_address(addr)
    if level == 1:
        # 最初の「市」「区」「町」「村」「郡」まで
        m = re.match(r'(.+?(?:市|区|町|村|郡))', norm)
        return m.group(1) if m else norm[:10]
    elif level == 2:
        # 町名まで（数字の前まで）
        m = re.match(r'(.+?(?:丁目|番|号|[0-9]))', norm)
        return m.group(1) if m else norm[:20]
    else:
        # 番地まで（30文字でカット）
        return norm[:30]


def extract_corp_name(facility_name: str) -> Optional[str]:
    """施設名から法人名を抽出"""
    parts = re.split(r'[\s　]+', facility_name.strip())

    # スペース区切りで前半が法人名
    if len(parts) >= 2:
        for prefix in CORP_PREFIXES:
            if parts[0].startswith(prefix):
                return parts[0]
        # 「医療法人　〇〇会　△△病院」→「医療法人〇〇会」
        if len(parts) >= 3:
            combined = parts[0] + parts[1]
            for prefix in CORP_PREFIXES:
                if combined.startswith(prefix):
                    return combined

    # スペースなし: 「〇〇会」で切る
    for prefix in CORP_PREFIXES:
        if facility_name.startswith(prefix):
            rest = facility_name[len(prefix):]
            m = re.match(r'(.+?(?:会|園|社|組|舎|団))', rest)
            if m:
                return prefix + m.group(1)
            break

    return None


def run():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # === Step 1: 施設データ読み込み ===
    c.execute("SELECT id, name, address, facility_type FROM facilities")
    facilities = c.fetchall()
    print(f"施設数: {len(facilities):,}")

    # 法人名ルックアップ
    name_lookup = defaultdict(list)  # norm_corp_name -> [(fid, addr)]
    # 住所ルックアップ
    addr_lookup = defaultdict(list)  # addr_key -> [(fid, name, facility_type)]

    for fid, fname, faddr, ftype in facilities:
        corp = extract_corp_name(fname)
        if corp:
            name_lookup[normalize(corp)].append((fid, faddr or ""))

        if faddr:
            for level in [3, 2]:
                key = addr_key(faddr, level)
                if key:
                    addr_lookup[key].append((fid, fname, ftype))

    print(f"法人名抽出: {sum(len(v) for v in name_lookup.values()):,}件, ユニーク: {len(name_lookup):,}")
    print(f"住所キー: {len(addr_lookup):,}件")

    # === Step 2: 国税庁CSVストリーム ===
    csv_files = sorted(HOUJIN_DIR.glob("*.csv"))
    if not csv_files:
        print(f"ERROR: No CSV files in {HOUJIN_DIR}")
        sys.exit(1)

    matches = {}  # fid -> corp_number
    csv_total = 0

    for csv_file in csv_files:
        print(f"\nStreaming {csv_file.name}...")
        with open(csv_file, encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 13:
                    continue
                corp_number = row[1]
                corp_name = row[6]
                # 住所は都道府県(9)+市区町村(10)+番地(11)を結合
                corp_addr = (row[9] if len(row) > 9 else "") + \
                            (row[10] if len(row) > 10 else "") + \
                            (row[11] if len(row) > 11 else "")

                if not corp_number or not corp_name:
                    continue

                csv_total += 1
                if csv_total % 1000000 == 0:
                    print(f"  ...{csv_total:,}行, マッチ: {len(matches):,}")

                norm_name = normalize(corp_name)

                # Phase 1: 法人名完全一致
                candidates = name_lookup.get(norm_name)
                if candidates:
                    if len(candidates) == 1:
                        fid, _ = candidates[0]
                        if fid not in matches:
                            matches[fid] = corp_number
                    else:
                        # 同名→住所で絞り込み
                        norm_caddr = normalize_address(corp_addr) if corp_addr else ""
                        for fid, faddr in candidates:
                            if fid in matches:
                                continue
                            if norm_caddr and faddr:
                                norm_faddr = normalize_address(faddr)
                                if (norm_caddr[:15] in norm_faddr or
                                        norm_faddr[:15] in norm_caddr):
                                    matches[fid] = corp_number

                # Phase 2: 住所マッチ（医療関連法人のみ）
                if corp_addr:
                    is_medical = any(corp_name.startswith(p) for p in MEDICAL_CORP_PREFIXES)
                    if is_medical:
                        for level in [3, 2]:
                            key = addr_key(corp_addr, level)
                            fac_candidates = addr_lookup.get(key)
                            if fac_candidates:
                                for fid, fname, ftype in fac_candidates:
                                    if fid in matches:
                                        continue
                                    # 法人種別と施設種別の整合性チェック
                                    if _type_compatible(corp_name, ftype):
                                        matches[fid] = corp_number

    print(f"\nCSV読み込み完了: {csv_total:,}法人")
    print(f"マッチ: {len(matches):,}")

    # === Step 3: DB更新 ===
    c.execute("UPDATE facilities SET corporate_number = NULL")
    updates = [(cn, fid) for fid, cn in matches.items()]
    c.executemany("UPDATE facilities SET corporate_number = ? WHERE id = ?", updates)
    conn.commit()

    # 統計
    type_names = {1: '病院', 2: '診療所', 3: '歯科', 4: '助産所', 5: '薬局'}
    c.execute("""
        SELECT facility_type, COUNT(*) as total, COUNT(corporate_number) as matched
        FROM facilities GROUP BY facility_type ORDER BY facility_type
    """)
    print(f"\n=== 最終結果 ===")
    gt, gm = 0, 0
    for ft, tot, mat in c.fetchall():
        print(f"  {type_names.get(ft, ft)}: {mat:,}/{tot:,} ({mat/tot*100:.1f}%)")
        gt += tot
        gm += mat
    print(f"  合計: {gm:,}/{gt:,} ({gm/gt*100:.1f}%)")

    conn.close()


def _type_compatible(corp_name: str, facility_type: int) -> bool:
    """法人種別と施設種別が整合するかチェック"""
    # 薬局(5)→株式会社/有限会社/医療法人OK
    # 病院(1)/診療所(2)→医療法人系OK
    # 歯科(3)→医療法人系OK
    # 助産所(4)→あまり法人化されてない
    if facility_type in (1, 2, 3):
        return any(corp_name.startswith(p) for p in [
            '医療法人', '社会医療法人', '特定医療法人',
            '社会福祉法人', '独立行政法人', '地方独立行政法人',
            '国立大学法人', '学校法人',
            '一般社団法人', '一般財団法人', '公益社団法人', '公益財団法人',
            '特定非営利活動法人',
        ])
    elif facility_type == 5:  # 薬局
        return any(corp_name.startswith(p) for p in [
            '株式会社', '有限会社', '合同会社', '医療法人',
            '一般社団法人', '一般財団法人',
        ])
    elif facility_type == 4:  # 助産所
        return any(corp_name.startswith(p) for p in [
            '医療法人', '一般社団法人',
        ])
    return False


if __name__ == "__main__":
    print("=== 法人番号マッチング v2（名称+住所）===")
    run()
