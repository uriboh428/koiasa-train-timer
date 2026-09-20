import datetime
import html
import urllib.parse
from typing import List, Dict, Any, Optional

JST = datetime.timezone(datetime.timedelta(hours=9))

def get_timestamp_ms(dt: datetime.datetime) -> int:
    """JST準拠のUNIXエポックミリ秒を取得"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return int(dt.timestamp() * 1000)

def escape_text(text: object) -> str:
    """XSS防止のためのHTML特殊文字エスケープ"""
    if text is None:
        return ""
    return html.escape(str(text))

def is_safe_url(url: str) -> bool:
    """外部リンクの安全プロトコル検証（http/https限定）"""
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in ("http", "https")
from timetable_data import (
    KOIGAKUBO_DEPARTURES,
    KOKUBUNJI_CHUO_DOWN,
    NISHI_KOKUBUNJI_MUSASHINO_UP,
    KITA_ASAKADAI_MUSASHINO_DOWN,
    NISHI_KOKUBUNJI_CHUO_UP,
    KOKUBUNJI_SEIBU_DOWN,
)

def get_default_direction(now: Optional[datetime.datetime] = None) -> str:
    """
    アクセス時刻（JST）に応じたスマートなデフォルト行き先を判定
    - 01:00 〜 12:00: 「恋ヶ窪 ➡ 朝霞台」（午前・出勤時間帯）
    - 12:01 〜 24:59（翌00:59）: 「朝霞台 ➡ 恋ヶ窪」（午後・帰宅時間帯・深夜便）
    """
    if now is None:
        now = datetime.datetime.now(JST)
    mins = now.hour * 60 + now.minute
    # 01:00 = 60分, 12:00 = 720分
    if 60 <= mins <= 720:
        return "koigakubo_to_asakadai"
    else:
        return "asakadai_to_koigakubo"


def find_next_departure(schedule: Dict[int, List[int]], after_time: datetime.datetime) -> Optional[datetime.datetime]:
    """指定時刻以降で最も近い発車時刻を検索"""
    current_hour = after_time.hour
    current_min = after_time.minute
    current_sec = after_time.second

    for offset in range(24):
        target_hour = (current_hour + offset) % 24
        minutes = schedule.get(target_hour, [])
        for m in minutes:
            if offset == 0:
                if m > current_min or (m == current_min and current_sec == 0):
                    return after_time.replace(hour=target_hour, minute=m, second=0, microsecond=0)
            else:
                days_add = (current_hour + offset) // 24
                target_date = after_time + datetime.timedelta(days=days_add)
                return target_date.replace(hour=target_hour, minute=m, second=0, microsecond=0)
    return None

def find_next_departures_list(
    schedule: Dict[int, List[int]], after_time: datetime.datetime, count: int = 3
) -> List[datetime.datetime]:
    """指定時刻以降の直近便リストを取得"""
    results = []
    check_time = after_time
    for _ in range(count):
        nxt = find_next_departure(schedule, check_time)
        if not nxt:
            break
        results.append(nxt)
        check_time = nxt + datetime.timedelta(minutes=1)
    return results

def get_transfer_buffer(station: str, pace: str = "normal") -> int:
    """乗換ペースに応じたバッファ分数"""
    if station == "kokubunji":
        return 2 if pace == "fast" else 5 if pace == "relaxed" else 3
    else:  # nishi_kokubunji
        return 3 if pace == "fast" else 6 if pace == "relaxed" else 4

def calculate_koigakubo_to_asakadai(
    dept_time: datetime.datetime, pace: str, now: datetime.datetime
) -> Dict[str, Any]:
    """往路：恋ヶ窪 ➡ 朝霞台 の計算"""
    leg1_dept = dept_time
    leg1_arrv = leg1_dept + datetime.timedelta(minutes=3)

    buf_k = get_transfer_buffer("kokubunji", pace)
    earliest_chuo = leg1_arrv + datetime.timedelta(minutes=buf_k)
    leg2_dept = find_next_departure(KOKUBUNJI_CHUO_DOWN, earliest_chuo) or earliest_chuo
    leg2_arrv = leg2_dept + datetime.timedelta(minutes=2)

    buf_n = get_transfer_buffer("nishi_kokubunji", pace)
    earliest_m = leg2_arrv + datetime.timedelta(minutes=buf_n)
    leg3_dept = find_next_departure(NISHI_KOKUBUNJI_MUSASHINO_UP, earliest_m) or earliest_m
    leg3_arrv = leg3_dept + datetime.timedelta(minutes=22)

    final_arrv = leg3_arrv + datetime.timedelta(minutes=1)  # 北朝霞〜朝霞台 徒歩1分
    total_min = round((final_arrv - leg1_dept).total_seconds() / 60)
    seconds_left = max(0, int((leg1_dept - now).total_seconds()))

    legs = [
        {
            "line": "西武国分寺線",
            "code": "SK",
            "color": "#00965c",
            "dest": "国分寺行",
            "from_station": "恋ヶ窪",
            "from_time": leg1_dept.strftime("%H:%M"),
            "to_station": "国分寺",
            "to_time": leg1_arrv.strftime("%H:%M"),
            "duration": 3,
            "wait_min": round((leg2_dept - leg1_arrv).total_seconds() / 60),
            "platform": "1・2番線",
            "note": "西武線改札からJR中央線ホームへ乗り換え",
        },
        {
            "line": "JR中央線快速",
            "code": "JC",
            "color": "#ff6600",
            "dest": "高尾・八王子方面行",
            "from_station": "国分寺",
            "from_time": leg2_dept.strftime("%H:%M"),
            "to_station": "西国分寺",
            "to_time": leg2_arrv.strftime("%H:%M"),
            "duration": 2,
            "wait_min": round((leg3_dept - leg2_arrv).total_seconds() / 60),
            "platform": "1番線 (下り)",
            "note": "階段またはエスカレーターで武蔵野線ホームへ直行",
        },
        {
            "line": "JR武蔵野線",
            "code": "JM",
            "color": "#e65a00",
            "dest": "南船橋・東京方面行",
            "from_station": "西国分寺",
            "from_time": leg3_dept.strftime("%H:%M"),
            "to_station": "北朝霞 (朝霞台)",
            "to_time": leg3_arrv.strftime("%H:%M"),
            "duration": 22,
            "platform": "3番線",
            "note": "改札を出て右手の階段上が朝霞台駅（東武東上線）",
        },
    ]

    return {
        "direction": "koigakubo_to_asakadai",
        "departure_time": leg1_dept.strftime("%H:%M"),
        "arrival_time": final_arrv.strftime("%H:%M"),
        "total_minutes": total_min,
        "seconds_until_departure": seconds_left,
        "departure_timestamp_ms": get_timestamp_ms(leg1_dept),
        "legs": legs,
    }

def calculate_asakadai_to_koigakubo(
    dept_time: datetime.datetime, pace: str, now: datetime.datetime
) -> Dict[str, Any]:
    """復路：朝霞台 ➡ 恋ヶ窪 の計算"""
    leg1_dept = dept_time
    leg1_arrv = leg1_dept + datetime.timedelta(minutes=22)

    buf_n = get_transfer_buffer("nishi_kokubunji", pace)
    earliest_c = leg1_arrv + datetime.timedelta(minutes=buf_n)
    leg2_dept = find_next_departure(NISHI_KOKUBUNJI_CHUO_UP, earliest_c) or earliest_c
    leg2_arrv = leg2_dept + datetime.timedelta(minutes=2)

    buf_k = get_transfer_buffer("kokubunji", pace)
    earliest_s = leg2_arrv + datetime.timedelta(minutes=buf_k)
    leg3_dept = find_next_departure(KOKUBUNJI_SEIBU_DOWN, earliest_s) or earliest_s
    leg3_arrv = leg3_dept + datetime.timedelta(minutes=3)

    total_min = round((leg3_arrv - leg1_dept).total_seconds() / 60)
    seconds_left = max(0, int((leg1_dept - now).total_seconds()))

    legs = [
        {
            "line": "JR武蔵野線",
            "code": "JM",
            "color": "#e65a00",
            "dest": "府中本町行",
            "from_station": "朝霞台 (北朝霞)",
            "from_time": leg1_dept.strftime("%H:%M"),
            "to_station": "西国分寺",
            "to_time": leg1_arrv.strftime("%H:%M"),
            "duration": 22,
            "wait_min": round((leg2_dept - leg1_arrv).total_seconds() / 60),
            "platform": "1番線 (府中本町方面)",
            "note": "階段を下りて中央線上りホーム（東京・新宿方面）へ",
        },
        {
            "line": "JR中央線快速",
            "code": "JC",
            "color": "#ff6600",
            "dest": "新宿・東京方面行",
            "from_station": "西国分寺",
            "from_time": leg2_dept.strftime("%H:%M"),
            "to_station": "国分寺",
            "to_time": leg2_arrv.strftime("%H:%M"),
            "duration": 2,
            "wait_min": round((leg3_dept - leg2_arrv).total_seconds() / 60),
            "platform": "2番線 (上り)",
            "note": "西武線連絡改札へ進む",
        },
        {
            "line": "西武国分寺線",
            "code": "SK",
            "color": "#00965c",
            "dest": "東村山行",
            "from_station": "国分寺",
            "from_time": leg3_dept.strftime("%H:%M"),
            "to_station": "恋ヶ窪",
            "to_time": leg3_arrv.strftime("%H:%M"),
            "duration": 3,
            "platform": "5番線 (西武ホーム)",
            "note": "1駅で恋ヶ窪駅へ到着します",
        },
    ]

    return {
        "direction": "asakadai_to_koigakubo",
        "departure_time": leg1_dept.strftime("%H:%M"),
        "arrival_time": leg3_arrv.strftime("%H:%M"),
        "total_minutes": total_min,
        "seconds_until_departure": seconds_left,
        "departure_timestamp_ms": get_timestamp_ms(leg1_dept),
        "legs": legs,
    }

def get_routes(
    direction: str, offset_minutes: int = 0, pace: str = "normal", now: Optional[datetime.datetime] = None
) -> List[Dict[str, Any]]:
    """指定方向の直近便リストを取得"""
    if now is None:
        now = datetime.datetime.now()
    search_time = now + datetime.timedelta(minutes=offset_minutes)

    if direction == "koigakubo_to_asakadai":
        depts = find_next_departures_list(KOIGAKUBO_DEPARTURES, search_time, 3)
        return [calculate_koigakubo_to_asakadai(d, pace, now) for d in depts]
    else:
        depts = find_next_departures_list(KITA_ASAKADAI_MUSASHINO_DOWN, search_time, 3)
        return [calculate_asakadai_to_koigakubo(d, pace, now) for d in depts]

def get_last_train_info(
    direction: str, now: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    """本日の終電案内およびカウントダウン情報を取得"""
    if now is None:
        now = datetime.datetime.now()

    if direction == "koigakubo_to_asakadai":
        # 恋ヶ窪発 朝霞台行 最終接続便: 恋ヶ窪 00:03 発 ➡ 朝霞台 00:45 着
        # 0:03 発は日付としては「翌日未明」
        # 当日 05:00 〜 23:59 の場合、終電は翌日 00:03
        # 当日 00:00 〜 00:03 の場合、終電は当日 00:03
        # 当日 00:04 〜 04:59 の場合、当日の終電は運行終了
        base_date = now.date()
        if now.hour < 5:
            # 0時〜4時台
            last_dept_dt = now.replace(hour=0, minute=3, second=0, microsecond=0)
            if now > last_dept_dt:
                is_expired = True
                seconds_left = 0
            else:
                is_expired = False
                seconds_left = int((last_dept_dt - now).total_seconds())
        else:
            # 5時〜23時台
            tomorrow = base_date + datetime.timedelta(days=1)
            last_dept_dt = datetime.datetime.combine(tomorrow, datetime.time(0, 3))
            if now.tzinfo:
                last_dept_dt = last_dept_dt.replace(tzinfo=now.tzinfo)
            is_expired = False
            seconds_left = int((last_dept_dt - now).total_seconds())

        return {
            "direction": "koigakubo_to_asakadai",
            "departure_station": "恋ヶ窪",
            "destination_station": "朝霞台",
            "departure_time": "00:03",
            "arrival_time": "00:45",
            "total_minutes": 42,
            "seconds_until_last_train": seconds_left,
            "is_expired": is_expired,
            "route_summary": "恋ヶ窪 00:03 (西武) ➡ 国分寺 00:10 (中央) ➡ 西国分寺 00:22 (武蔵野) ➡ 朝霞台 00:45",
            "first_train_time": "05:12",
        }
    else:
        # 朝霞台発 恋ヶ窪行 最終接続便: 北朝霞(朝霞台) 23:45 発 ➡ 恋ヶ窪 00:34 着
        # 当日 05:00 〜 23:45 の場合、終電は当日 23:45
        # 当日 23:46 〜 翌 04:59 の場合、運行終了
        base_date = now.date()
        if now.hour < 5:
            # 0時〜4時台（昨晩の終電は終了済み）
            is_expired = True
            seconds_left = 0
        else:
            last_dept_dt = now.replace(hour=23, minute=45, second=0, microsecond=0)
            if now > last_dept_dt:
                is_expired = True
                seconds_left = 0
            else:
                is_expired = False
                seconds_left = int((last_dept_dt - now).total_seconds())

        return {
            "direction": "asakadai_to_koigakubo",
            "departure_station": "朝霞台",
            "destination_station": "恋ヶ窪",
            "departure_time": "23:45",
            "arrival_time": "00:34",
            "total_minutes": 49,
            "seconds_until_last_train": seconds_left,
            "is_expired": is_expired,
            "route_summary": "朝霞台 23:45 (武蔵野) ➡ 西国分寺 00:10 (中央) ➡ 国分寺 00:31 (西武) ➡ 恋ヶ窪 00:34",
            "first_train_time": "05:14",
        }

