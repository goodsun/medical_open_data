"""open_now フィルタ — 現在診療中の施設を判定

DB非依存のロジック。Specialty.scheduleのJSON構造を解析する。
"""
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# Python weekday() → schedule key
WEEKDAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def is_open_now(schedules: list, now: datetime = None) -> bool:
    """複数のschedule(JSON dict)のうち、いずれかが現在診療中ならTrue。
    
    schedules: [{"mon": {"start": "09:00", "end": "17:30"}, ...}, ...]
    """
    if now is None:
        now = datetime.now(JST)

    day_key = WEEKDAY_MAP[now.weekday()]
    current_time = now.strftime("%H:%M")

    for schedule in schedules:
        if not isinstance(schedule, dict):
            continue
        slot = schedule.get(day_key)
        if not slot or not isinstance(slot, dict):
            continue
        start = slot.get("start")
        end = slot.get("end")
        if start and end and start <= current_time <= end:
            return True

    return False
