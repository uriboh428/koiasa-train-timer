"""
恋朝トレインタイマー (Koiasa Train Timer)
恋ヶ窪 ⇔ 朝霞台 リアルタイム電車ナビゲーション・ダッシュボード
Streamlit Webアプリケーション（地中海オーシャンブルー × すりガラスUI版）
"""

import os
import sys
import datetime
import html
import urllib.parse
from typing import List, Dict, Any, Optional
import streamlit as st

# プロジェクトルートのパスを検索パスの最優先に追加（Streamlit Cloud必須）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 日本標準時（JST: UTC+9）を厳格に定義（クラウドサーバーUTC対応）
JST = datetime.timezone(datetime.timedelta(hours=9))

# セキュリティヘルパー関数（XSS対策・URL安全検証）
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

# ==========================================
# 公式ダイヤグラムデータ（完全自己完結内包）
# ==========================================
KOIGAKUBO_DEPARTURES = {
    5: [12, 32, 50],
    6: [5, 17, 27, 37, 47, 56],
    7: [5, 14, 22, 30, 38, 46, 54],
    8: [2, 10, 18, 26, 35, 45, 55],
    9: [5, 15, 25, 35, 45, 55],
    10: [5, 15, 25, 35, 45, 55],
    11: [5, 15, 25, 35, 45, 55],
    12: [5, 15, 25, 35, 45, 55],
    13: [5, 15, 25, 35, 45, 55],
    14: [5, 15, 25, 35, 45, 55],
    15: [5, 15, 25, 35, 45, 55],
    16: [5, 15, 25, 35, 45, 55],
    17: [4, 12, 20, 28, 36, 44, 52],
    18: [0, 8, 16, 24, 32, 40, 48, 56],
    19: [4, 12, 20, 28, 36, 44, 52],
    20: [1, 10, 20, 30, 40, 50],
    21: [2, 14, 26, 38, 50],
    22: [2, 15, 28, 41, 54],
    23: [8, 23, 41],
    0: [3, 24],
}

KOKUBUNJI_CHUO_DOWN = {
    5: [5, 20, 35, 48],
    6: [1, 12, 21, 30, 38, 45, 52, 58],
    7: [4, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
    8: [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
    9: [1, 6, 12, 17, 23, 28, 34, 40, 46, 52, 58],
    10: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    11: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    12: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    13: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    14: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    15: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    16: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    17: [3, 8, 14, 19, 25, 30, 36, 42, 48, 54],
    18: [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
    19: [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
    20: [1, 7, 13, 19, 25, 31, 37, 43, 49, 55],
    21: [2, 9, 16, 23, 30, 38, 46, 54],
    22: [2, 10, 18, 27, 36, 46, 56],
    23: [7, 18, 30, 43, 56],
    0: [10, 27, 46],
}

NISHI_KOKUBUNJI_MUSASHINO_UP = {
    5: [7, 24, 41, 55],
    6: [9, 21, 32, 42, 51],
    7: [1, 10, 19, 28, 37, 46, 54],
    8: [3, 12, 21, 30, 40, 50],
    9: [1, 12, 23, 34, 45, 56],
    10: [7, 18, 29, 40, 51],
    11: [3, 14, 25, 36, 47, 58],
    12: [9, 20, 31, 42, 53],
    13: [4, 15, 26, 37, 48, 59],
    14: [10, 21, 32, 43, 54],
    15: [5, 16, 27, 38, 49],
    16: [0, 11, 22, 33, 44, 55],
    17: [5, 15, 24, 33, 42, 51],
    18: [0, 9, 18, 27, 36, 45, 54],
    19: [3, 12, 21, 30, 40, 50],
    20: [1, 12, 23, 34, 45, 56],
    21: [7, 19, 31, 43, 55],
    22: [8, 22, 36, 51],
    23: [6, 22, 40],
    0: [1, 22],
}

KITA_ASAKADAI_MUSASHINO_DOWN = {
    5: [14, 31, 47],
    6: [2, 15, 27, 37, 46, 55],
    7: [4, 13, 21, 29, 37, 45, 53],
    8: [1, 9, 18, 27, 36, 46, 56],
    9: [6, 17, 28, 39, 50],
    10: [1, 12, 23, 34, 45, 56],
    11: [7, 18, 29, 40, 51],
    12: [2, 13, 24, 35, 46, 57],
    13: [8, 19, 30, 41, 52],
    14: [3, 14, 25, 36, 47, 58],
    15: [9, 20, 31, 42, 53],
    16: [4, 15, 26, 37, 47, 57],
    17: [7, 17, 26, 35, 44, 53],
    18: [2, 11, 20, 29, 38, 47, 56],
    19: [5, 14, 23, 32, 42, 52],
    20: [2, 13, 24, 35, 46, 57],
    21: [9, 21, 33, 46, 59],
    22: [12, 26, 41, 56],
    23: [12, 28, 45],
    0: [7, 28],
}

NISHI_KOKUBUNJI_CHUO_UP = {
    5: [8, 23, 37, 49],
    6: [0, 10, 19, 27, 35, 42, 49, 56],
    7: [2, 8, 13, 18, 23, 28, 33, 38, 43, 48, 53, 58],
    8: [3, 8, 13, 18, 23, 28, 33, 38, 43, 48, 53, 58],
    9: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    10: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    11: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    12: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    13: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    14: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    15: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    16: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    17: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    18: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    19: [4, 10, 16, 22, 28, 34, 40, 46, 52, 58],
    20: [4, 10, 16, 23, 30, 38, 46, 54],
    21: [2, 10, 19, 28, 37, 47, 57],
    22: [7, 18, 29, 41, 53],
    23: [6, 20, 36, 52],
    0: [10, 30],
}

KOKUBUNJI_SEIBU_DOWN = {
    5: [18, 38, 56],
    6: [11, 23, 33, 43, 53],
    7: [1, 10, 19, 27, 35, 43, 51, 59],
    8: [7, 15, 23, 32, 41, 51],
    9: [1, 11, 21, 31, 41, 51],
    10: [1, 11, 21, 31, 41, 51],
    11: [1, 11, 21, 31, 41, 51],
    12: [1, 11, 21, 31, 41, 51],
    13: [1, 11, 21, 31, 41, 51],
    14: [1, 11, 21, 31, 41, 51],
    15: [1, 11, 21, 31, 41, 51],
    16: [1, 11, 21, 31, 41, 51],
    17: [0, 8, 16, 24, 32, 40, 48, 56],
    18: [4, 12, 20, 28, 36, 44, 52],
    19: [0, 8, 16, 24, 32, 40, 48, 56],
    20: [5, 15, 25, 35, 45, 55],
    21: [7, 19, 31, 43, 55],
    22: [8, 21, 34, 47],
    23: [1, 15, 30, 48],
    0: [10, 31],
}

LINE_INFO = [
    {"name": "西武国分寺線", "operator": "西武鉄道", "status": "平常運行", "url": "https://www.seiburailway.jp/railwayinfo/"},
    {"name": "JR中央線（快速）", "operator": "JR東日本", "status": "平常運行", "url": "https://traininfo.jreast.co.jp/train_info/kanto.aspx"},
    {"name": "JR武蔵野線", "operator": "JR東日本", "status": "平常運行", "url": "https://traininfo.jreast.co.jp/train_info/kanto.aspx"},
    {"name": "東武東上線", "operator": "東武鉄道", "status": "平常運行", "url": "https://www.tobu.co.jp/railway/guide/unko/"},
]

# ==========================================
# リアルタイム計算ロジック
# ==========================================
def find_next_departure(schedule: Dict[int, List[int]], after_time: datetime.datetime) -> Optional[datetime.datetime]:
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
    if station == "kokubunji":
        return 2 if pace == "fast" else 5 if pace == "relaxed" else 3
    else:
        return 3 if pace == "fast" else 6 if pace == "relaxed" else 4

def calculate_koigakubo_to_asakadai(
    dept_time: datetime.datetime, pace: str, now: datetime.datetime
) -> Dict[str, Any]:
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

    final_arrv = leg3_arrv + datetime.timedelta(minutes=1)
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
        "legs": legs,
    }

def calculate_asakadai_to_koigakubo(
    dept_time: datetime.datetime, pace: str, now: datetime.datetime
) -> Dict[str, Any]:
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
        "legs": legs,
    }

def get_routes(
    direction: str, offset_minutes: int = 0, pace: str = "normal", now: Optional[datetime.datetime] = None
) -> List[Dict[str, Any]]:
    if now is None:
        now = datetime.datetime.now(JST)
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
        now = datetime.datetime.now(JST)

    base_date = now.date()
    if direction == "koigakubo_to_asakadai":
        # 恋ヶ窪 ➡ 朝霞台 最終連絡便: 恋ヶ窪 00:03 発 ➡ 朝霞台 00:45 着
        if now.hour < 5:
            last_dept_dt = now.replace(hour=0, minute=3, second=0, microsecond=0)
            if now > last_dept_dt:
                is_expired = True
                seconds_left = 0
            else:
                is_expired = False
                seconds_left = int((last_dept_dt - now).total_seconds())
        else:
            tomorrow = base_date + datetime.timedelta(days=1)
            last_dept_dt = datetime.datetime.combine(tomorrow, datetime.time(0, 3)).replace(tzinfo=now.tzinfo)
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
        # 朝霞台 ➡ 恋ヶ窪 最終連絡便: 朝霞台 23:45 発 ➡ 恋ヶ窪 00:34 着
        if now.hour < 5:
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

# ==========================================
# Streamlit UI 表示部
# ==========================================
st.set_page_config(
    page_title="恋朝トレインタイマー | 恋ヶ窪 ⇔ 朝霞台",
    page_icon="🚆",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 地中海オーシャンブルー × すりガラス調 × Material Icons スタイリング
st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
<style>
    html, body, [class*="css"] {
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Hiragino Sans", "Meiryo", sans-serif;
    }
    .material-symbols-outlined {
        font-family: 'Material Symbols Outlined' !important;
        font-weight: normal;
        font-style: normal;
        font-size: 20px;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        vertical-align: middle;
        -webkit-font-smoothing: antialiased;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2.5rem;
        max-width: 600px;
    }
    .ocean-header {
        background: linear-gradient(135deg, #003B5C 0%, #004B73 40%, #0071A4 100%);
        color: #FFFFFF;
        padding: 22px 24px;
        border-radius: 24px;
        margin-bottom: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 75, 115, 0.28);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(16px);
    }
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.95);
        padding: 16px 18px;
        border-radius: 20px;
        border: 1px solid rgba(226, 232, 240, 0.9);
        box-shadow: 0 4px 18px -2px rgba(0, 75, 115, 0.06);
        backdrop-filter: blur(12px);
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 800;
        color: #004B73;
        font-size: 1.85rem !important;
    }
    .last-train-card {
        background: linear-gradient(135deg, rgba(0, 75, 115, 0.03) 0%, rgba(255, 127, 80, 0.06) 100%);
        border: 1.5px solid rgba(255, 127, 80, 0.35);
        border-radius: 20px;
        padding: 14px 18px;
        margin: 14px 0 18px 0;
        box-shadow: 0 4px 16px -2px rgba(255, 127, 80, 0.12);
        backdrop-filter: blur(10px);
    }
    .leg-card {
        background: rgba(255, 255, 255, 0.96);
        border-radius: 18px;
        padding: 15px 18px;
        margin: 10px 0;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 10px rgba(0, 75, 115, 0.04);
        backdrop-filter: blur(8px);
    }
    .stButton > button {
        border-radius: 16px;
        font-weight: 700;
        border: none;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(0, 75, 115, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if "direction" not in st.session_state:
    st.session_state["direction"] = "koigakubo_to_asakadai"
if "offset_minutes" not in st.session_state:
    st.session_state["offset_minutes"] = 0
if "pace" not in st.session_state:
    st.session_state["pace"] = "normal"
if "selected_index" not in st.session_state:
    st.session_state["selected_index"] = 0

# 日本標準時（JST）の現在時刻
now_jst = datetime.datetime.now(JST)
time_str = now_jst.strftime("%H:%M:%S")
date_str = now_jst.strftime("%Y年%m月%d日")

st.markdown(f"""
<div class="ocean-header">
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
            <div style="font-size:0.75rem; font-weight:700; letter-spacing:0.1em; opacity:0.85; text-transform:uppercase; display:flex; align-items:center; gap:4px;">
                <span class="material-symbols-outlined" style="font-size:16px; color:#7DD3FC;">schedule</span>
                Realtime Transit Dashboard
            </div>
            <h1 style="margin:4px 0 2px 0; font-size:1.65rem; font-weight:900; color:white; letter-spacing:-0.02em; display:flex; align-items:center; gap:8px;">
                <span class="material-symbols-outlined" style="font-size:28px; color:#38BDF8;">train</span>
                恋朝トレインタイマー
            </h1>
            <p style="margin:0; font-size:0.85rem; opacity:0.92;">恋ヶ窪 ⇔ 朝霞台 リアルタイム発着予測</p>
        </div>
        <div style="text-align:right;">
            <div style="background:rgba(255,255,255,0.18); padding:5px 12px; border-radius:12px; font-size:0.75rem; font-weight:700; display:inline-flex; align-items:center; gap:4px; border:1px solid rgba(255,255,255,0.25);">
                <span class="material-symbols-outlined" style="font-size:14px; color:#34D399;">check_circle</span>
                平常運行
            </div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:0.88rem; font-weight:700; margin-top:5px; letter-spacing:0.02em;">
                {time_str}
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 進行方向コントロール
col_dir, col_rev = st.columns([3, 1])
with col_dir:
    dir_options = ["恋ヶ窪 ➡ 朝霞台", "朝霞台 ➡ 恋ヶ窪"]
    current_label = "恋ヶ窪 ➡ 朝霞台" if st.session_state["direction"] == "koigakubo_to_asakadai" else "朝霞台 ➡ 恋ヶ窪"
    selected_label = st.radio(
        "進行方向",
        options=dir_options,
        index=0 if current_label == "恋ヶ窪 ➡ 朝霞台" else 1,
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state["direction"] = "koigakubo_to_asakadai" if selected_label == "恋ヶ窪 ➡ 朝霞台" else "asakadai_to_koigakubo"

with col_rev:
    if st.button("🔄 反転", use_container_width=True, help="行き先を逆にする"):
        st.session_state["direction"] = (
            "asakadai_to_koigakubo" if st.session_state["direction"] == "koigakubo_to_asakadai" else "koigakubo_to_asakadai"
        )
        st.session_state["selected_index"] = 0
        st.rerun()

# 出発オフセット ＆ 乗換ペース（折りたたみ・設定）
with st.expander("⚙️ 出発タイミング ＆ 乗換設定", expanded=False):
    c_off, c_pace = st.columns(2)
    with c_off:
        st.session_state["offset_minutes"] = st.select_slider(
            "何分後に出発？",
            options=[0, 5, 10, 15, 30],
            format_func=lambda x: "今すぐ" if x == 0 else f"+{x}分後",
            value=st.session_state["offset_minutes"]
        )
    with c_pace:
        pace_map = {"fast": "急ぎ足（最短接続）", "normal": "標準（おすすめ）", "relaxed": "ゆったり（余裕重視）"}
        st.session_state["pace"] = st.selectbox(
            "乗換ゆとり度",
            options=["normal", "fast", "relaxed"],
            format_func=lambda x: pace_map.get(x, x),
            index=0 if st.session_state["pace"] == "normal" else 1 if st.session_state["pace"] == "fast" else 2
        )

# 経路計算実行
routes = get_routes(
    direction=st.session_state["direction"],
    offset_minutes=st.session_state["offset_minutes"],
    pace=st.session_state["pace"],
    now=now_jst
)

if not routes:
    st.warning("本日の運行は終了いたしました。")
    st.stop()

# 選択されたルート
selected_idx = min(st.session_state["selected_index"], len(routes) - 1)
current_route = routes[selected_idx]

wait_seconds = current_route["seconds_until_departure"]
wait_min = wait_seconds // 60
wait_sec = wait_seconds % 60
is_urgent = wait_seconds <= 120

# メインメトリクス表示（発車まで・発車時刻・到着予想）
m1, m2, m3 = st.columns(3)
with m1:
    st.metric(
        label="発車までの時間",
        value=f"{wait_min:02d}分{wait_sec:02d}秒",
        delta="まもなく発車" if is_urgent else f"あと{wait_min}分",
        delta_color="inverse" if is_urgent else "normal"
    )
with m2:
    dept_label = "恋ヶ窪発" if st.session_state["direction"] == "koigakubo_to_asakadai" else "朝霞台発"
    st.metric(
        label=f"出発時刻 ({dept_label})",
        value=current_route["departure_time"],
        help="発車時刻"
    )
with m3:
    arrv_label = "朝霞台着" if st.session_state["direction"] == "koigakubo_to_asakadai" else "恋ヶ窪着"
    st.metric(
        label=f"到着予想 ({arrv_label})",
        value=current_route["arrival_time"],
        delta=f"所要 {current_route['total_minutes']}分"
    )

if is_urgent:
    st.error("⚠️ まもなく発車時刻です！乗り遅れにご注意ください。")

# 本日の終電案内 ＆ カウントダウンカード（新設）
last_train = get_last_train_info(st.session_state["direction"], now=now_jst)
if last_train["is_expired"]:
    st.markdown(f"""
    <div class="last-train-card" style="border-color:#CBD5E1; background:rgba(241,245,249,0.75);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:700; font-size:0.9rem; color:#64748B; display:flex; align-items:center; gap:6px;">
                <span class="material-symbols-outlined" style="font-size:18px; color:#94A3B8;">bedtime</span>
                本日の終電（最終連絡便）
            </div>
            <div style="font-size:0.8rem; color:#64748B; font-weight:700;">
                本日の運行終了（始発 {last_train['first_train_time']}）
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    lt_sec = last_train["seconds_until_last_train"]
    lt_hours = lt_sec // 3600
    lt_mins = (lt_sec % 3600) // 60
    lt_urgent = (lt_sec <= 1800)  # 30分以内
    lt_time_badge = f"あと {lt_hours}時間{lt_mins:02d}分" if lt_hours > 0 else f"あと {lt_mins}分！"
    lt_badge_bg = "#EF4444" if lt_urgent else "#004B73"
    
    st.markdown(f"""
    <div class="last-train-card" style="border-left: 5px solid {lt_badge_bg};">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div style="font-weight:800; font-size:0.92rem; color:#004B73; display:flex; align-items:center; gap:6px;">
                <span class="material-symbols-outlined" style="font-size:20px; color:{lt_badge_bg};">bedtime</span>
                本日の終電（最終連絡便）
            </div>
            <div style="background:{lt_badge_bg}; color:white; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:800; letter-spacing:0.02em; display:inline-flex; align-items:center; gap:3px;">
                <span class="material-symbols-outlined" style="font-size:13px;">timer</span>
                {lt_time_badge}
            </div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
            <div style="font-size:1.12rem; font-weight:800; color:#0F172A;">
                {escape_text(last_train['departure_station'])} <span style="font-family:'JetBrains Mono'; color:#004B73; font-size:1.3rem; margin-left:2px;">{last_train['departure_time']}</span> 発
                <span style="font-size:0.85rem; color:#64748B; margin:0 6px;">➡</span>
                {escape_text(last_train['destination_station'])} <span style="font-family:'JetBrains Mono'; color:#059669; font-size:1.3rem; margin-left:2px;">{last_train['arrival_time']}</span> 着
            </div>
            <div style="font-size:0.8rem; font-weight:700; color:#64748B;">
                所要 {last_train['total_minutes']}分
            </div>
        </div>
        <div style="font-size:0.75rem; color:#334155; background:rgba(255,255,255,0.85); padding:6px 12px; border-radius:10px; display:flex; align-items:center; gap:6px; border:1px solid rgba(226,232,240,0.8);">
            <span class="material-symbols-outlined" style="font-size:15px; color:#0071A4;">route</span>
            <span>{escape_text(last_train['route_summary'])}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 乗り継ぎルート詳細（タイムライン）
st.markdown("""
<div style="display:flex; align-items:center; gap:6px; margin: 20px 0 10px 0;">
    <span class="material-symbols-outlined" style="color:#004B73; font-size:22px;">alt_route</span>
    <h3 style="margin:0; font-size:1.15rem; font-weight:800; color:#004B73;">乗り継ぎルート詳細</h3>
</div>
""", unsafe_allow_html=True)

for idx, leg in enumerate(current_route["legs"]):
    line_name = escape_text(leg['line'])
    dest = escape_text(leg['dest'])
    from_st = escape_text(leg['from_station'])
    to_st = escape_text(leg['to_station'])
    f_time = escape_text(leg['from_time'])
    t_time = escape_text(leg['to_time'])
    duration = leg['duration']
    color = leg['color']
    platform = escape_text(leg.get('platform', ''))
    note = escape_text(leg.get('note', ''))
    wait_m = leg.get('wait_min', 0)

    st.markdown(f"""
    <div class="leg-card" style="border-left: 6px solid {color};">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <div style="font-weight:800; font-size:1.05rem; color:#0F172A; display:flex; align-items:center; flex-wrap:wrap; gap:4px;">
                <span>{from_st}</span>
                <span style="font-family:'JetBrains Mono'; color:#004B73; font-size:1.1rem; margin-left:4px;">{f_time} 発</span>
                <span style="font-size:0.75rem; color:#64748B; background:#F1F5F9; padding:2px 8px; border-radius:6px; margin-left:4px; display:inline-flex; align-items:center; gap:2px;">
                    <span class="material-symbols-outlined" style="font-size:13px;">signpost</span>{platform}
                </span>
            </div>
            <div style="font-size:0.8rem; font-weight:700; color:{color}; display:inline-flex; align-items:center; gap:2px;">
                <span class="material-symbols-outlined" style="font-size:14px;">timer</span>乗車 {duration}分
            </div>
        </div>
        <div style="font-size:0.85rem; font-weight:700; color:{color}; margin-bottom:4px; display:flex; align-items:center; gap:4px;">
            <span class="material-symbols-outlined" style="font-size:16px;">train</span>
            <span>{line_name}（{dest}）</span>
        </div>
        <div style="font-size:0.75rem; color:#64748B; display:flex; align-items:center; gap:4px;">
            <span class="material-symbols-outlined" style="font-size:14px; color:#94A3B8;">info</span>
            <span>{note}</span>
        </div>
        <div style="margin-top:6px; font-weight:800; font-size:1.05rem; color:#0F172A; display:flex; align-items:center; gap:4px;">
            <span class="material-symbols-outlined" style="font-size:16px; color:#059669;">arrow_forward</span>
            <span>{to_st}</span>
            <span style="font-family:'JetBrains Mono'; color:#059669; font-size:1.1rem; margin-left:4px;">{t_time} 着</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if idx < len(current_route["legs"]) - 1 and wait_m > 0:
        badge = "✨ スムーズ接続" if wait_m <= 4 else f"待ち時間 {wait_m}分"
        st.markdown(f"""
        <div style="margin:-2px 0 6px 18px; font-size:0.8rem; font-weight:700; color:#0071A4; display:flex; align-items:center; gap:4px;">
            <span class="material-symbols-outlined" style="font-size:16px; color:#0084B4;">directions_walk</span>
            <span>乗り換え待ち: 約 <strong>{wait_m}</strong> 分 ({badge})</span>
        </div>
        """, unsafe_allow_html=True)

# その後の電車候補（比較・選択）
if len(routes) > 1:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:6px; margin: 20px 0 10px 0;">
        <span class="material-symbols-outlined" style="color:#004B73; font-size:22px;">view_timeline</span>
        <h3 style="margin:0; font-size:1.15rem; font-weight:800; color:#004B73;">その後の電車候補</h3>
    </div>
    """, unsafe_allow_html=True)
    cols = st.columns(len(routes))
    for i, r in enumerate(routes):
        with cols[i]:
            is_cur = (i == selected_idx)
            label = "最速便" if i == 0 else f"+{i}本後"
            btn_text = f"{label}\n{r['departure_time']} ➡ {r['arrival_time']}"
            if st.button(btn_text, key=f"btn_route_{i}", use_container_width=True, type="primary" if is_cur else "secondary"):
                st.session_state["selected_index"] = i
                st.rerun()

# 運行情報インスペクター
with st.expander("ℹ️ 関連路線の運行状況・公式リンク", expanded=False):
    for line in LINE_INFO:
        col_name, col_stat, col_link = st.columns([3, 2, 2])
        with col_name:
            st.markdown(f"**{escape_text(line['name'])}** ({escape_text(line['operator'])})")
        with col_stat:
            st.markdown(f"<span style='color:#059669; font-weight:700; display:inline-flex; align-items:center; gap:3px;'><span class='material-symbols-outlined' style='font-size:14px;'>check_circle</span>{escape_text(line['status'])}</span>", unsafe_allow_html=True)
        with col_link:
            if is_safe_url(line['url']):
                st.markdown(f"<a href='{line['url']}' target='_blank' rel='noopener noreferrer' style='text-decoration:none; color:#0071A4; font-weight:700; font-size:0.85rem; display:inline-flex; align-items:center; gap:2px;'>公式運行情報 <span class='material-symbols-outlined' style='font-size:14px;'>open_in_new</span></a>", unsafe_allow_html=True)

st.markdown("---")
if st.button("🔄 最新の時刻で再計算・更新", use_container_width=True):
    st.rerun()

st.markdown("""
<div style="text-align:center; color:#94A3B8; font-size:0.75rem; margin-top:20px;">
    恋朝トレインタイマー © 2026<br>
    東証公式J-Quantsスクリーナー統一アーキテクチャ準拠
</div>
""", unsafe_allow_html=True)

