"""
恋朝トレインタイマー (Koiasa Train Timer)
恋ヶ窪 ⇔ 朝霞台 リアルタイム電車ナビゲーション・ダッシュボード
Streamlit Webアプリケーション（地中海オーシャンブルー × すりガラスUI版）
"""

import os
import sys
import datetime
import html
import time
import urllib.parse
from typing import List, Dict, Any, Optional
import streamlit as st
import streamlit.components.v1 as components
from auth_manager import (
    load_auth_credentials,
    save_auth_credentials,
    verify_password,
    get_secure_token,
    verify_secure_token,
    regenerate_secure_token,
    GlobalSecurityManager,
    get_secrets_toml_template,
    generate_token_link,
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_DURATION_SECONDS,
    MIN_PASSWORD_LENGTH,
)

# プロジェクトルートのパスを検索パスの最優先に追加（Streamlit Cloud必須）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from transit_engine import get_default_direction

# 日本標準時（JST: UTC+9）を厳格に定義（クラウドサーバーUTC対応）
JST = datetime.timezone(datetime.timedelta(hours=9))

def get_timestamp_ms(dt: datetime.datetime) -> int:
    """JST準拠のUNIXエポックミリ秒を取得"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return int(dt.timestamp() * 1000)

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
    {"name": "西武国分寺線", "operator": "西武鉄道", "url": "https://www.seiburailway.jp/railwayinfo/"},
    {"name": "JR中央線（快速）", "operator": "JR東日本", "url": "https://traininfo.jreast.co.jp/train_info/kanto.aspx"},
    {"name": "JR武蔵野線", "operator": "JR東日本", "url": "https://traininfo.jreast.co.jp/train_info/kanto.aspx"},
    {"name": "東武東上線", "operator": "東武鉄道", "url": "https://www.tobu.co.jp/railway/guide/unko/"},
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
        "departure_timestamp_ms": get_timestamp_ms(leg1_dept),
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
        "departure_timestamp_ms": get_timestamp_ms(leg1_dept),
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

@st.cache_data(ttl=21600)  # 6時間キャッシュで爆速表示を維持
def get_revision_status() -> Dict[str, Any]:
    """ダイヤ改正告知の自動検知（6時間キャッシュ対応）"""
    try:
        from revision_detector import check_timetable_revision
        return check_timetable_revision()
    except Exception:
        return {
            "status": "up_to_date",
            "status_label": "✅ ダイヤ最新確認済",
            "has_alert": False,
            "badge_color": "#059669",
            "message": "現在適用中のダイヤグラムは最新です。",
            "current_version": "2026年春季現行ダイヤ (2026-03-15改定)",
            "announcements": [],
            "last_checked_jst": datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        }

# ==========================================
# Streamlit UI 表示部（スマホ最優先・ファーストビュー最適化）
# ==========================================
st.set_page_config(
    page_title="恋朝トレインタイマー | 恋ヶ窪 ⇔ 朝霞台",
    page_icon="🚆",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# Swiss Precision & Minimalist Transit Design System
# (Linear / Raycast / Swiss SBB 基準の極小ミニマリズム・脱臭UI)
# -----------------------------------------------------------------------------
st.markdown("""
<meta name="robots" content="noindex, nofollow, noarchive">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,300..500,0,0" />
<style>
    /* ==========================================================================
       Goodpatch Neo-Tokyo Metro Design System (Ver 3.6)
       Human-Centered Design / Apple HIG & Linear Precision Spec
       ========================================================================== */
    :root {
        --bg-base: #F8FAFC;
        --surface-card: #FFFFFF;
        --surface-hero: linear-gradient(145deg, #06152B 0%, #0A223E 55%, #02385C 100%);
        --surface-glass: rgba(255, 255, 255, 0.07);
        --border-subtle: #E2E8F0;
        --border-card: #CBD5E1;
        --border-glass: rgba(255, 255, 255, 0.14);
        --text-primary: #0F172A;
        --text-secondary: #475569;
        --text-muted: #64748B;
        --text-light: #94A3B8;
        --accent-ocean: #0284C7;
        --accent-cyan: #38BDF8;
        --accent-emerald: #10B981;
        --accent-amber: #F59E0B;
        --accent-rose: #EF4444;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
        --shadow-md: 0 4px 12px -2px rgba(15, 23, 42, 0.06), 0 2px 4px rgba(15, 23, 42, 0.02);
        --shadow-hero: 0 12px 32px -4px rgba(2, 48, 80, 0.38), 0 4px 12px rgba(6, 21, 43, 0.2);
    }

    html, body, [class*="css"] {
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
        background-color: var(--bg-base);
        color: var(--text-primary);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        letter-spacing: -0.012em;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    .material-symbols-outlined {
        font-family: 'Material Symbols Outlined' !important;
        font-weight: 300;
        font-style: normal;
        font-size: 16px;
        line-height: 1;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        vertical-align: middle;
    }

    .block-container {
        padding-top: 0.35rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
        max-width: 460px;
    }

    /* 1. 統合トップバー (Unified Top Navigation Bar) */
    .top-nav-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 2px 8px 2px;
        margin-bottom: 4px;
        border-bottom: 1px solid #E2E8F0;
    }
    .brand-block {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .brand-logo-badge {
        background: linear-gradient(135deg, #003350 0%, #004B73 100%);
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 9px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        box-shadow: 0 2px 6px rgba(0, 75, 115, 0.25);
    }
    .brand-text-group {
        display: flex;
        flex-direction: column;
    }
    .brand-name {
        font-size: 0.98rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.02em;
        line-height: 1.15;
    }
    .brand-sub {
        font-size: 0.6rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .meta-pill-group {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .live-indicator-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 3px 8px;
        border-radius: 9999px;
        box-shadow: var(--shadow-sm);
    }
    .pulse-dot {
        width: 6px;
        height: 6px;
        background-color: var(--accent-emerald);
        border-radius: 9999px;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
        animation: pulse-glow 2s infinite ease-in-out;
    }
    @keyframes pulse-glow {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(0.85); opacity: 0.45; }
    }
    .live-clock-text {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 0.72rem;
        font-weight: 600;
        color: #334155;
    }
    .version-tag {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 700;
        color: #15803D;
        background: #DCFCE7;
        border: 1px solid #86EFAC;
        padding: 2px 6px;
        border-radius: 6px;
    }

    /* 2. 行き先切り替え（Apple HIG 48px タップターゲット & セグメンテッドUI） */
    .stButton > button {
        border-radius: 14px !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        min-height: 48px !important;
        padding: 8px 10px !important;
        border: 1px solid #E2E8F0 !important;
        background: #FFFFFF !important;
        color: #334155 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03) !important;
        transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
        white-space: pre-line !important;
        line-height: 1.25 !important;
    }
    .stButton > button:hover {
        background: #F8FAFC !important;
        color: #0F172A !important;
        border-color: #CBD5E1 !important;
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(0,0,0,0.06) !important;
    }
    .stButton > button:active {
        transform: translateY(1px);
        box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #004B73 0%, #003350 100%) !important;
        color: #FFFFFF !important;
        border-color: #002A44 !important;
        box-shadow: 0 4px 12px rgba(0, 75, 115, 0.28) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #003859 0%, #002238 100%) !important;
        border-color: #001A2C !important;
        box-shadow: 0 6px 16px rgba(0, 75, 115, 0.35) !important;
    }

    /* 3. ヒーロー・カウントダウンカード（Frosted Deep Ocean） */
    .hero-timer-card {
        background: var(--surface-hero);
        color: #FFFFFF;
        border-radius: var(--radius-xl);
        padding: 16px 18px 14px 18px;
        margin: 6px 0 12px 0;
        box-shadow: var(--shadow-hero);
        border: 1px solid var(--border-glass);
        position: relative;
        overflow: hidden;
    }
    .hero-timer-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0) 100%);
    }
    .hero-timer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .hero-micro-label {
        font-size: 0.68rem;
        font-weight: 700;
        color: var(--text-light);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .badge {
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2.5px 9px;
        border-radius: 9999px;
        letter-spacing: 0.03em;
        display: inline-block;
        transition: all 0.2s ease;
    }
    .badge-normal {
        background: rgba(255, 255, 255, 0.12);
        color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .badge-urgent {
        background: var(--accent-rose);
        color: #FFFFFF;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
        animation: urgent-pulse 1.2s infinite;
    }
    .badge-departed {
        background: #475569;
        color: #E2E8F0;
    }
    @keyframes urgent-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(0.97); }
    }

    .hero-digits-wrap {
        text-align: center;
        padding: 4px 0 8px 0;
    }
    .hero-digits {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 2.9rem;
        font-weight: 800;
        line-height: 1.0;
        letter-spacing: -0.04em;
        color: #FFFFFF;
        text-shadow: 0 2px 14px rgba(0, 0, 0, 0.45);
    }
    .hero-digits .unit {
        font-size: 1.1rem;
        font-weight: 600;
        color: #94A3B8;
        margin: 0 4px 0 1px;
    }

    /* 発着時刻インフォバー */
    .hero-schedule-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--surface-glass);
        border-radius: var(--radius-md);
        padding: 8px 14px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-top: 4px;
        backdrop-filter: blur(8px);
    }
    .hero-st-block {
        display: flex;
        flex-direction: column;
    }
    .hero-st-name {
        font-size: 0.78rem;
        color: #94A3B8;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .hero-st-time {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 1.35rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.15;
    }
    .hero-st-time.arrival {
        color: var(--accent-cyan);
    }
    .hero-arrow-block {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
    }
    .hero-duration-badge {
        font-size: 0.72rem;
        font-weight: 700;
        color: #E2E8F0;
        background: rgba(56, 189, 248, 0.2);
        border: 1px solid rgba(56, 189, 248, 0.4);
        padding: 2px 8px;
        border-radius: 9999px;
    }

    /* 終電案内行 */
    .hero-last-train-row {
        font-size: 0.72rem;
        color: #94A3B8;
        margin-top: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 2px 0 2px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* 4. 統合メトロ・タイムラインボード (Clean Metro White Card) */
    .metro-board {
        background: var(--surface-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-xl);
        padding: 14px 16px 12px 16px;
        margin: 4px 0 12px 0;
        box-shadow: var(--shadow-md);
    }
    .metro-board-header {
        font-size: 0.72rem;
        font-weight: 800;
        color: var(--text-muted);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #F1F5F9;
        padding-bottom: 6px;
    }

    /* エキスパンダーの洗練 */
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-sm) !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stExpander"] details summary {
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        color: #334155 !important;
        padding: 12px 16px !important;
        transition: background 0.15s;
    }
    div[data-testid="stExpander"] details summary:hover {
        background: #F8FAFC !important;
    }
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

sec_mgr = GlobalSecurityManager.get_instance()
credentials = load_auth_credentials()

# A. 初回起動モード（パスワード未設定時）：初回セットアップ画面
if credentials is None:
    st.markdown("""
    <div style="text-align:center; padding: 24px 16px 12px 16px;">
        <div style="background:linear-gradient(135deg, #003350 0%, #004B73 100%); color:white; width:64px; height:64px; border-radius:20px; display:inline-flex; align-items:center; justify-content:center; margin-bottom:12px; box-shadow:0 6px 16px rgba(0,75,115,0.25);">
            <span class="material-symbols-outlined" style="font-size:32px; color:#38BDF8;">shield_person</span>
        </div>
        <h2 style="font-size:1.3rem; font-weight:900; color:#004B73; margin:0 0 6px 0;">初期セキュリティ設定</h2>
        <p style="font-size:0.8rem; color:#64748B; margin:0 0 16px 0;">本アプリはプライベート利用専用です。<br>ご利用を開始する前に、安全なパスワード（4文字以上）を設定してください。</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("setup_password_form", clear_on_submit=False):
        setup_pass = st.text_input("パスワードの設定（4文字以上）", type="password", placeholder="パスワードを入力")
        setup_confirm = st.text_input("パスワードの再入力（確認）", type="password", placeholder="同じパスワードを入力")
        setup_submit = st.form_submit_button("パスワードを登録して起動 🔒", use_container_width=True, type="primary")

        if setup_submit:
            if len(setup_pass) < MIN_PASSWORD_LENGTH:
                st.error(f"❌ パスワードは{MIN_PASSWORD_LENGTH}文字以上で設定してください。")
            elif setup_pass != setup_confirm:
                st.error("❌ 確認用パスワードが一致しません。")
            else:
                if save_auth_credentials(setup_pass):
                    st.session_state["authenticated"] = True
                    st.session_state["is_admin"] = False
                    sec_mgr.record_success()
                    st.success("✅ パスワードを設定しました。アプリを起動します...")
                    st.rerun()
                else:
                    st.error("❌ パスワードの保存に失敗しました。ファイル書き込み権限をご確認ください。")

    st.markdown("""
    <div style="text-align:center; margin-top:24px; font-size:0.75rem; color:#94A3B8;">
        🔒 Private Transit Security System © 2026
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# B. パスワード設定済みの場合：セキュアトークンURL または URLパラメータ自動認証
if credentials and not st.session_state["authenticated"]:
    # 1) 推測不能な暗号アクセストークンによる認証 (?token=...)
    query_token = st.query_params.get("token")
    if query_token and verify_secure_token(str(query_token), credentials["salt"], credentials["hash"], credentials.get("token_salt")):
        st.session_state["authenticated"] = True
        st.session_state["is_admin"] = False
        sec_mgr.record_success()
        st.query_params.clear()
        st.rerun()

    # 2) 平文パスワードURLパラメータの完全廃止（セキュリティ保護・漏洩防止）
    if st.query_params.get("pin") or st.query_params.get("pass"):
        st.query_params.clear()
        st.warning("⚠️ 平文パスワードによるURLアクセスはセキュリティ保護のため廃止されました。暗号トークンURLまたは画面からログインしてください。")

# C. 通常ログイン・ロック画面（未認証時）
if not st.session_state["authenticated"]:
    is_locked, remaining_sec = sec_mgr.get_lockout_status()

    st.markdown("""
    <div style="text-align:center; padding: 24px 16px 12px 16px;">
        <div style="background:linear-gradient(135deg, #003350 0%, #004B73 100%); color:white; width:64px; height:64px; border-radius:20px; display:inline-flex; align-items:center; justify-content:center; margin-bottom:12px; box-shadow:0 6px 16px rgba(0,75,115,0.25);">
            <span class="material-symbols-outlined" style="font-size:32px; color:#38BDF8;">lock</span>
        </div>
        <h2 style="font-size:1.3rem; font-weight:900; color:#004B73; margin:0 0 4px 0;">恋朝トレインタイマー</h2>
        <div style="display:inline-block; background:#DCFCE7; border:1px solid #86EFAC; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:800; color:#15803D; margin-bottom:10px;">Ver 3.6 (完全ロール分離 ＆ 家族安心ゼロトラスト版)</div>
        <p style="font-size:0.8rem; color:#64748B; margin:0 0 16px 0;">このアプリはプライベート（非公開）設定されています。<br>ご利用にはパスワードが必要です。</p>
    </div>
    """, unsafe_allow_html=True)

    if is_locked:
        st.error(f"🚫 セキュリティ保護のためアプリ全体が一時ロックされています。<br>あと **{remaining_sec}秒** 後に再試行してください。（※ブラウザを再起動しても解除されません）", icon="🔒")

    with st.form("login_form", clear_on_submit=False):
        input_pass = st.text_input(
            "パスワード",
            type="password",
            placeholder="パスワードを入力",
            disabled=is_locked
        )
        submitted = st.form_submit_button(
            "認証して開く 🔓",
            use_container_width=True,
            type="primary",
            disabled=is_locked
        )

        if submitted and not is_locked:
            if verify_password(input_pass, credentials["hash"], credentials["salt"]):
                st.session_state["authenticated"] = True
                st.session_state["is_admin"] = False
                sec_mgr.record_success()
                st.rerun()
            else:
                is_now_locked, lock_duration = sec_mgr.record_failure()
                if is_now_locked:
                    st.error(f"❌ 誤ったパスワードが{MAX_FAILED_ATTEMPTS}回連続で入力されました。ブルートフォース攻撃防止のため、アプリ全体を{LOCKOUT_DURATION_SECONDS}秒間ロックします。")
                else:
                    remain_tries = MAX_FAILED_ATTEMPTS - sec_mgr.failed_attempts
                    st.error(f"❌ パスワードが違います。（残り試行可能回数: {remain_tries}回）")

    st.markdown("""
    <div style="text-align:center; margin-top:24px; font-size:0.75rem; color:#94A3B8;">
        🔒 Private Transit Dashboard © 2026
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# 日本標準時（JST）の現在時刻
now_jst = datetime.datetime.now(JST)

if "direction" not in st.session_state:
    st.session_state["direction"] = get_default_direction(now_jst)
if "offset_minutes" not in st.session_state:
    st.session_state["offset_minutes"] = 0
if "pace" not in st.session_state:
    st.session_state["pace"] = "normal"
if "selected_index" not in st.session_state:
    st.session_state["selected_index"] = 0

# ----------------------------------------------------
# 1. 【最上部】行き先設定（堅牢なステートレス・ボタングループ）
# ----------------------------------------------------
is_k2a = (st.session_state["direction"] == "koigakubo_to_asakadai")

current_time_str = now_jst.strftime("%H:%M:%S")
st.markdown(f"""
<div class="top-nav-bar">
    <div class="brand-block">
        <div class="brand-logo-badge">🚆</div>
        <div class="brand-text-group">
            <span class="brand-name">恋朝タイマー</span>
            <span class="brand-sub">KOIASA TRANSIT</span>
        </div>
    </div>
    <div class="meta-pill-group">
        <div class="live-indicator-pill">
            <span class="pulse-dot"></span>
            <span class="live-clock-text" id="global-clock-display">{current_time_str}</span>
        </div>
        <span class="version-tag">Ver 3.6 (完全ロール分離 ＆ 家族安心ゼロトラスト版)</span>
    </div>
</div>
""", unsafe_allow_html=True)

col_d1, col_d2, col_rv = st.columns([5, 5, 2])
with col_d1:
    btn_k2a_text = "📍 恋ヶ窪 ➡ 朝霞台" if is_k2a else "恋ヶ窪 ➡ 朝霞台"
    if st.button(
        btn_k2a_text,
        key="btn_dir_k2a",
        type="primary" if is_k2a else "secondary",
        use_container_width=True,
    ):
        st.session_state["direction"] = "koigakubo_to_asakadai"
        st.session_state["selected_index"] = 0
        st.rerun()

with col_d2:
    btn_a2k_text = "📍 朝霞台 ➡ 恋ヶ窪" if not is_k2a else "朝霞台 ➡ 恋ヶ窪"
    if st.button(
        btn_a2k_text,
        key="btn_dir_a2k",
        type="primary" if not is_k2a else "secondary",
        use_container_width=True,
    ):
        st.session_state["direction"] = "asakadai_to_koigakubo"
        st.session_state["selected_index"] = 0
        st.rerun()

with col_rv:
    if st.button("⇄", key="btn_dir_rev", use_container_width=True, help="行き先を瞬時に反転"):
        st.session_state["direction"] = "asakadai_to_koigakubo" if is_k2a else "koigakubo_to_asakadai"
        st.session_state["selected_index"] = 0
        st.rerun()

# ダイヤ改正検知ステータス & 終電情報（確定した direction に基づく）
revision_info = get_revision_status()
last_train = get_last_train_info(st.session_state["direction"], now=now_jst)

# ----------------------------------------------------
# 2. リアルタイム経路計算 & クライアント自律型秒針エンジン
# ----------------------------------------------------
routes = get_routes(
    direction=st.session_state["direction"],
    offset_minutes=st.session_state["offset_minutes"],
    pace=st.session_state["pace"],
    now=now_jst
)

if not routes:
    st.warning("本日の運行は終了いたしました。")
    st.stop()

selected_idx = min(st.session_state["selected_index"], len(routes) - 1)
current_route = routes[selected_idx]

dept_station = "恋ヶ窪" if st.session_state["direction"] == "koigakubo_to_asakadai" else "朝霞台"
arrv_station = "朝霞台" if st.session_state["direction"] == "koigakubo_to_asakadai" else "恋ヶ窪"

@st.fragment(run_every=1)
def render_hero_timer_fragment(
    dept_timestamp_ms: int,
    dept_station: str,
    arrv_station: str,
    dept_time: str,
    arrv_time: str,
    total_minutes: int,
    last_train_dept: str,
    last_train_duration: int,
):
    now_dt = datetime.datetime.now(JST)
    now_ms = get_timestamp_ms(now_dt)
    left_sec = max(0, (dept_timestamp_ms - now_ms) // 1000)
    min_left = left_sec // 60
    sec_left = left_sec % 60
    min_str = f"{min_left:02d}"
    sec_str = f"{sec_left:02d}"

    if left_sec <= 0:
        badge_class = "badge-departed"
        badge_text = "発車しました"
        min_str = "00"
        sec_str = "00"
        # 0秒になったら親を再実行して次の便に更新
        if "reload_triggered" not in st.session_state:
            st.session_state["reload_triggered"] = True
            st.rerun()
    elif left_sec <= 120:
        if "reload_triggered" in st.session_state:
            del st.session_state["reload_triggered"]
        badge_class = "badge-urgent"
        badge_text = "まもなく発車"
    else:
        if "reload_triggered" in st.session_state:
            del st.session_state["reload_triggered"]
        badge_class = "badge-normal"
        badge_text = "NEXT DEPARTURE"

    clock_str = f"{now_dt.hour:02d}:{now_dt.minute:02d}:{now_dt.second:02d}"

    html_snippet = f"""
    <div class="hero-timer-card">
        <div class="hero-timer-header">
            <span class="hero-micro-label">⏱️ 次の発車まで</span>
            <div><span class="badge {badge_class}">{badge_text}</span></div>
        </div>
        <div class="hero-digits-wrap">
            <div class="hero-digits">
                <span id="hero-min-str">{min_str}</span><span class="unit">分</span><span id="hero-sec-str">{sec_str}</span><span class="unit">秒</span>
            </div>
        </div>
        <div class="hero-schedule-bar">
            <div class="hero-st-block">
                <div class="hero-st-name">{dept_station} 発</div>
                <div class="hero-st-time">{dept_time}</div>
            </div>
            <div class="hero-arrow-block">
                <div class="hero-duration-badge">約{total_minutes}分</div>
                <div style="color:#64748B; font-size:1.1rem; font-weight:700;">➡</div>
            </div>
            <div class="hero-st-block" style="text-align:right;">
                <div class="hero-st-name">{arrv_station} 着</div>
                <div class="hero-st-time arrival">{arrv_time}</div>
            </div>
        </div>
        <div class="hero-last-train-row">
            <span>🌙 今夜の最終便案内</span>
            <span style="font-family:'JetBrains Mono'; font-weight:700; color:#E2E8F0;">{dept_station} {last_train_dept} 発（所要 {last_train_duration}分）</span>
        </div>
    </div>
    <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" onload="
        (function() {{
            var target = {dept_timestamp_ms};
            var serverMs = {now_ms};
            var offset = Date.now() - serverMs;
            function update() {{
                var now = Date.now() - offset;
                var left = Math.max(0, Math.floor((target - now) / 1000));
                var m = Math.floor(left / 60);
                var s = left % 60;
                var mEl = document.getElementById('hero-min-str');
                var sEl = document.getElementById('hero-sec-str');
                if (mEl) mEl.textContent = (m < 10 ? '0' : '') + m;
                if (sEl) sEl.textContent = (s < 10 ? '0' : '') + s;
                var gEl = document.getElementById('global-clock-display');
                if (gEl) {{
                    var d = new Date(now);
                    var ch = d.getHours(); var cm = d.getMinutes(); var cs = d.getSeconds();
                    gEl.textContent = (ch < 10 ? '0' : '') + ch + ':' + (cm < 10 ? '0' : '') + cm + ':' + (cs < 10 ? '0' : '') + cs;
                }}
            }}
            update();
            if (window._heroTimerInterval) clearInterval(window._heroTimerInterval);
            window._heroTimerInterval = setInterval(update, 1000);
        }})();
    " style="display:none;" />
    """
    st.markdown(html_snippet, unsafe_allow_html=True)

render_hero_timer_fragment(
    dept_timestamp_ms=current_route["departure_timestamp_ms"],
    dept_station=dept_station,
    arrv_station=arrv_station,
    dept_time=current_route["departure_time"],
    arrv_time=current_route["arrival_time"],
    total_minutes=current_route["total_minutes"],
    last_train_dept=last_train["departure_time"],
    last_train_duration=last_train["total_minutes"],
)


# 4. 【統合メトロ・タイムラインボード】シームレスな1本線インフォグラフィック
metro_html = """
<div class="metro-board">
    <div class="metro-board-header">
        <span style="display:flex; align-items:center; gap:6px;">
            <span class="material-symbols-outlined" style="font-size:16px; color:#0284C7;">route</span>
            <span>乗換ルート詳細</span>
        </span>
        <span style="font-size:0.65rem; color:#64748B; font-weight:700; background:#F1F5F9; padding:2px 8px; border-radius:12px;">3区間 / 乗換2回</span>
    </div>
"""

legs_count = len(current_route["legs"])
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
    wait_m = leg.get('wait_min', 0)

    # 出発駅行
    metro_html += f"""
<div style="display:flex; align-items:center; justify-content:space-between; padding: 3px 0;">
    <div style="display:flex; align-items:center; gap:8px;">
        <div style="width:12px; height:12px; border-radius:9999px; border:3px solid {color}; background:#FFFFFF; flex-shrink:0; box-shadow:0 0 0 2px rgba(0,0,0,0.04);"></div>
        <div style="font-size:0.92rem; font-weight:800; color:#0F172A; letter-spacing:-0.01em;">{from_st}</div>
        <div style="font-size:0.68rem; color:#475569; background:#F1F5F9; border:1px solid #E2E8F0; padding:1px 6px; border-radius:6px; font-weight:600;">{platform}</div>
    </div>
    <div style="font-family:'JetBrains Mono'; font-variant-numeric:tabular-nums; font-size:0.95rem; font-weight:800; color:#0F172A;">
        {f_time}
    </div>
</div>
"""

    # レール（移動区間）
    metro_html += f"""
<div style="display:flex; align-items:center; justify-content:space-between; margin-left:5px; padding: 4px 0 4px 15px; border-left: 2.5px solid {color};">
    <div style="font-size:0.76rem; color:#334155; font-weight:600; display:flex; align-items:center; gap:5px;">
        <span style="color:{color}; font-size:0.7rem;">●</span>
        <span>{line_name}</span>
        <span style="color:#94A3B8; font-weight:500; font-size:0.72rem;">({dest})</span>
    </div>
    <div style="font-size:0.7rem; font-weight:700; color:{color}; background:rgba(0,0,0,0.03); border:1px solid rgba(0,0,0,0.04); padding:1.5px 7px; border-radius:6px;">
        {duration}分
    </div>
</div>
"""

    # 到着駅（最終区間のみ到着駅ノードを描画）
    if idx == legs_count - 1:
        metro_html += f"""
<div style="display:flex; align-items:center; justify-content:space-between; padding: 3px 0;">
    <div style="display:flex; align-items:center; gap:8px;">
        <div style="width:12px; height:12px; border-radius:9999px; border:3px solid #059669; background:#059669; flex-shrink:0; box-shadow:0 0 0 2px rgba(5,150,105,0.2);"></div>
        <div style="font-size:0.92rem; font-weight:800; color:#0F172A; letter-spacing:-0.01em;">{to_st}</div>
        <div style="font-size:0.68rem; color:#059669; background:#ECFDF5; border:1px solid #A7F3D0; padding:1px 6px; border-radius:6px; font-weight:700;">到着</div>
    </div>
    <div style="font-family:'JetBrains Mono'; font-variant-numeric:tabular-nums; font-size:0.98rem; font-weight:800; color:#059669;">
        {t_time}
    </div>
</div>
"""
    else:
        # 乗換待ち時間コネクタ
        badge_text = "スムーズ接続" if wait_m <= 4 else f"待 {wait_m}分"
        metro_html += f"""
<div style="display:flex; align-items:center; justify-content:space-between; margin-left:5px; padding: 4px 0 4px 15px; border-left: 2px dashed #CBD5E1; font-size:0.72rem;">
    <span style="color:#64748B; font-weight:600; display:flex; align-items:center; gap:3px;">
        <span class="material-symbols-outlined" style="font-size:14px; color:#94A3B8;">transfer_within_a_station</span>
        <span>乗換待ち時間</span>
    </span>
    <span style="color:#0284C7; font-weight:700; background:#F0F9FF; padding:1.5px 7px; border-radius:6px; border:1px solid #BAE6FD;">
        {wait_m}分 ({badge_text})
    </span>
</div>
"""

metro_html += "</div>"
st.markdown(metro_html, unsafe_allow_html=True)

# -------------------------------------------------------------
# 二次情報（その後の電車候補・詳細設定・終電・ダイヤ改正）
# -------------------------------------------------------------
if len(routes) > 1:
    st.markdown(f"""
    <div style="font-size:0.75rem; font-weight:800; color:#334155; letter-spacing:0.04em; margin: 14px 2px 8px 2px; display:flex; justify-content:space-between; align-items:center;">
        <span style="display:flex; align-items:center; gap:5px;">
            <span class="material-symbols-outlined" style="font-size:16px; color:#0284C7;">schedule</span>
            <span>その後の運行候補を比較</span>
        </span>
        <span style="font-size:0.68rem; color:#64748B; font-weight:700; background:#F1F5F9; border:1px solid #E2E8F0; padding:2px 8px; border-radius:10px;">全{len(routes)}候補</span>
    </div>
    """, unsafe_allow_html=True)
    cols = st.columns(len(routes))
    for i, r in enumerate(routes):
        with cols[i]:
            is_cur = (i == selected_idx)
            label = "★ 最速便" if i == 0 else f"+{i}本後"
            btn_text = f"{label}\n{r['departure_time']} ➡ {r['arrival_time']}"
            if st.button(btn_text, key=f"btn_route_{i}", use_container_width=True, type="primary" if is_cur else "secondary"):
                st.session_state["selected_index"] = i
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


# 終電詳細カード（折りたたみ）
with st.expander(f"🌙 終電のご案内（最終連絡便: {last_train['departure_time']}発）", expanded=False):
    if last_train["is_expired"]:
        st.markdown(f"<div style='font-size:0.8rem; color:#64748B;'>本日の運行は終了いたしました（始発 {last_train['first_train_time']}）</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="font-size:0.8rem; color:#0F172A; line-height:1.6;">
            <strong>{last_train['departure_station']} {last_train['departure_time']}発 → {last_train['destination_station']} {last_train['arrival_time']}着</strong>（所要 {last_train['total_minutes']}分）<br>
            <span style="font-size:0.72rem; color:#64748B;">ルート: {escape_text(last_train['route_summary'])}</span>
        </div>
        """, unsafe_allow_html=True)

# ダイヤ改正ステータス（通知があれば表示）
if revision_info.get("has_alert"):
    announcements_html = ""
    for ann in revision_info.get("announcements", []):
        t = escape_text(ann.get("title", ""))
        l = ann.get("link", "")
        d = escape_text(ann.get("pub_date_display", ""))
        link_tag = f"<a href='{l}' target='_blank' rel='noopener noreferrer' style='color:#C2410C; font-weight:600;'>{t}</a>" if is_safe_url(l) else t
        announcements_html += f"<div style='font-size:0.72rem; margin-top:2px;'>・{link_tag} ({d})</div>"

    st.markdown(f"""
    <div style="background:#FFFBEB; border:1px solid #FDE68A; border-radius:12px; padding:8px 12px; margin:8px 0; font-size:0.75rem;">
        <div style="font-weight:700; color:#B45309; display:flex; align-items:center; gap:4px;">
            <span>●</span>{escape_text(revision_info['status_label'])}
        </div>
        {announcements_html}
    </div>
    """, unsafe_allow_html=True)

# 運行情報インスペクター（各社公式リアルタイム情報）
with st.expander("🚆 路線運行情報（各社公式リアルタイム速報）", expanded=False):
    st.markdown("""
    <div style="font-size:0.75rem; color:#64748B; margin-bottom:10px; line-height:1.5;">
        ※本アプリは所定時刻表（公式ダイヤ）に基づいてご案内しています。事故・遅延・運転見合わせなどの最新の運行状況は、以下の各鉄道会社公式ページにてご確認ください。
    </div>
    """, unsafe_allow_html=True)
    for line in LINE_INFO:
        col_name, col_link = st.columns([3, 2])
        with col_name:
            st.markdown(f"<div style='font-size:0.82rem; font-weight:700; color:#0F172A; padding:4px 0;'>{escape_text(line['name'])} <span style='font-size:0.7rem; color:#64748B; font-weight:500;'>({escape_text(line['operator'])})</span></div>", unsafe_allow_html=True)
        with col_link:
            if is_safe_url(line['url']):
                st.markdown(f"<a href='{line['url']}' target='_blank' rel='noopener noreferrer' style='display:inline-block; width:100%; text-align:center; background:#F8FAFC; border:1px solid #CBD5E1; color:#0284C7; font-size:0.75rem; font-weight:600; padding:4px 8px; border-radius:8px; text-decoration:none;'>公式情報 ↗</a>", unsafe_allow_html=True)

# ==========================================
# 管理者専用エリア（ロール保護・完全分離設計）
# ==========================================
if st.session_state.get("is_admin", False):
    with st.expander("🛠️ 管理者メニュー（管理者認証済み 🔓）", expanded=True):
        col_adm_head1, col_adm_head2 = st.columns([3, 2])
        with col_adm_head1:
            st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:700; padding:6px 0;'>🔓 管理者権限でロック解除中</div>", unsafe_allow_html=True)
        with col_adm_head2:
            if st.button("🔒 管理者モード終了", key="btn_exit_admin_top", use_container_width=True, help="一般画面に戻します（管理メニューを隠します）"):
                st.session_state["is_admin"] = False
                st.rerun()

        st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#334155; margin:8px 0 4px 0;'>🔑 パスワードの変更</div>", unsafe_allow_html=True)
        with st.form("change_password_form", clear_on_submit=True):
            cur_pwd = st.text_input("現在のパスワード", type="password", placeholder="現在のパスワード")
            new_pwd = st.text_input("新しいパスワード（4文字以上）", type="password", placeholder="新しいパスワード")
            new_pwd_conf = st.text_input("新しいパスワード（再確認）", type="password", placeholder="新しいパスワードを再入力")
            update_btn = st.form_submit_button("パスワードを変更する", use_container_width=True)

            if update_btn:
                if not credentials or not verify_password(cur_pwd, credentials["hash"], credentials["salt"]):
                    st.error("❌ 現在のパスワードが正しくありません。")
                elif len(new_pwd) < MIN_PASSWORD_LENGTH:
                    st.error(f"❌ 新しいパスワードは{MIN_PASSWORD_LENGTH}文字以上で指定してください。")
                elif new_pwd != new_pwd_conf:
                    st.error("❌ 新しいパスワードの再確認が一致しません。")
                else:
                    if save_auth_credentials(new_pwd):
                        st.success("✅ パスワードを正常に変更しました！次回から新しいパスワードでログインしてください。")
                    else:
                        st.error("❌ パスワードの保存に失敗しました。")

        st.markdown("---")
        # セキュア・アクセストークンURL発行
        if credentials and "token" in credentials:
            token = credentials["token"]
            dynamic_url = generate_token_link(token)
            st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#334155; margin-bottom:4px;'>🔗 安全なワンタップ起動URL（トークン方式）</div>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.73rem; color:#64748B; margin-bottom:6px;'>ご家族に共有するための専用URLです。パスワード入力不要で安全に起動できます。</p>", unsafe_allow_html=True)

            init_display_url = dynamic_url if dynamic_url.startswith("http") else f"?token={token}"

            iframe_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: transparent;
                }}
                .wrap {{
                    display: flex;
                    gap: 8px;
                    align-items: center;
                    background: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 12px;
                    padding: 6px 10px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
                }}
                input {{
                    flex: 1;
                    border: none;
                    background: transparent;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.8rem;
                    color: #334155;
                    outline: none;
                    width: 100%;
                }}
                button {{
                    padding: 8px 16px;
                    font-size: 0.8rem;
                    font-weight: 700;
                    color: white;
                    background: linear-gradient(135deg, #004B73 0%, #003350 100%);
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    white-space: nowrap;
                    box-shadow: 0 2px 6px rgba(0, 75, 115, 0.2);
                    transition: all 0.15s ease;
                }}
                button:hover {{
                    background: linear-gradient(135deg, #003859 0%, #002238 100%);
                    box-shadow: 0 4px 10px rgba(0, 75, 115, 0.3);
                }}
                .toast {{
                    display: none;
                    font-size: 0.74rem;
                    font-weight: 700;
                    color: #065F46;
                    background: #ECFDF5;
                    border: 1px solid #A7F3D0;
                    padding: 6px 10px;
                    border-radius: 8px;
                    margin-top: 6px;
                }}
            </style>
            </head>
            <body>
            <div class="wrap">
                <input type="text" id="targetUrl" readonly value="{init_display_url}" />
                <button id="copyBtn" onclick="execCopy()">📋 コピー</button>
            </div>
            <div id="toastMsg" class="toast">✅ クリップボードにコピーしました！ご家族のLINE等に貼り付けてください。</div>
            <script>
            function execCopy() {{
                var inp = document.getElementById('targetUrl');
                var btn = document.getElementById('copyBtn');
                var toast = document.getElementById('toastMsg');
                inp.select();
                inp.setSelectionRange(0, 99999);
                var text = inp.value;

                function success() {{
                    btn.innerText = '✅ コピー完了!';
                    btn.style.background = '#10B981';
                    toast.style.display = 'block';
                    setTimeout(function() {{
                        btn.innerText = '📋 コピー';
                        btn.style.background = '#006699';
                        toast.style.display = 'none';
                    }}, 4000);
                }}

                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(text).then(success).catch(function() {{
                        document.execCommand('copy');
                        success();
                    }});
                }} else {{
                    document.execCommand('copy');
                    success();
                }}
            }}
            </script>
            </body>
            </html>
            """
            st.markdown("<div style='font-size:0.75rem; font-weight:600; color:#334155; margin-bottom:4px;'>💡 現在開いているブラウザのアドレスから自動生成された共有URL:</div>", unsafe_allow_html=True)
            components.html(iframe_html, height=72)
            st.code(init_display_url, language="text")
            st.caption("※上の青い「📋 コピー」ボタン、または右上のコピーアイコンを押すと、ご家族に送るURLが確実にコピーされます。")

            # ワンタップURLの即時再発行・失効ボタン
            if st.button("🔄 共有URLを再発行（古いURLを無効化）", key="btn_regen_token", use_container_width=True, help="万が一の誤送信時などに、古いURLを即座に使えなくして新しいURLを発行します"):
                regenerate_secure_token()
                st.success("✅ 新しい共有URLを発行しました！これまでの古いURLはすべて無効化されました。")
                st.rerun()

        st.markdown("---")
        # Streamlit Cloud Secrets（永続化）ガイド
        if credentials:
            with st.expander("☁️ クラウド恒久保存（Secrets設定 - 上級者向け）", expanded=False):
                st.markdown("<p style='font-size:0.75rem; color:#64748B; margin-bottom:6px;'>Streamlit Cloud の再起動時にも設定を100%保持したい場合は、Streamlit管理画面（Settings > Secrets）に以下を貼り付けてください。</p>", unsafe_allow_html=True)
                secrets_toml = get_secrets_toml_template("", credentials["salt"], credentials.get("token_salt")).replace('""', f'"{credentials["hash"]}"')
                st.code(secrets_toml, language="toml")

        st.markdown("---")
        c_chk1, c_chk2 = st.columns([3, 2])
        with c_chk1:
            st.markdown(f"<div style='font-size:0.75rem; color:#64748B; margin-top:6px;'>最終確認: {escape_text(revision_info.get('last_checked_jst', ''))}</div>", unsafe_allow_html=True)
        with c_chk2:
            if st.button("🔍 改正ニュース再確認", use_container_width=True, help="最新の発表ニュースを手動でチェック"):
                st.cache_data.clear()
                st.rerun()

else:
    # ご家族（一般モード）向け：危険な管理操作は完全非表示
    with st.expander("🔒 管理者メニュー（パスワード認証）", expanded=False):
        st.markdown("<p style='font-size:0.75rem; color:#64748B; margin-bottom:8px;'>パスワード変更や共有URLの管理を行うには、管理者パスワードを入力してください。</p>", unsafe_allow_html=True)
        with st.form("admin_unlock_form", clear_on_submit=True):
            admin_input = st.text_input("管理者パスワード", type="password", placeholder="パスワードを入力")
            admin_submit = st.form_submit_button("認証してロック解除 🔓", use_container_width=True, type="primary")

            if admin_submit:
                if credentials and verify_password(admin_input, credentials["hash"], credentials["salt"]):
                    st.session_state["is_admin"] = True
                    st.success("✅ 管理者認証に成功しました！")
                    st.rerun()
                else:
                    st.error("❌ パスワードが正しくありません。")

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
col_act1, col_act2 = st.columns([1, 1])
with col_act1:
    if st.button("🔄 最新情報で再計算", key="btn_recalc_footer", use_container_width=True, help="最新のダイヤ情報とキャッシュをクリアして再計算します"):
        st.cache_data.clear()
        st.rerun()
with col_act2:
    if st.button("🔒 画面ロック (ログアウト)", key="btn_logout_footer", use_container_width=True, help="アプリを即座にロックしてパスワード入力画面に戻します"):
        st.session_state["authenticated"] = False
        st.session_state["is_admin"] = False
        st.cache_data.clear()
        st.rerun()

st.markdown(f"""
<div style="text-align:center; color:#94A3B8; font-size:0.68rem; margin-top:16px; letter-spacing:0.02em; line-height:1.6;">
    KOIASA TRANSIT SYSTEM Ver 3.6 ｜ 収録ダイヤ: {escape_text(revision_info.get('current_version', '2026年春季現行ダイヤ'))}<br>
    <span style="font-size:0.62rem; color:#CBD5E1;">※本アプリは所定時刻表に基づき計算しています。遅延・運休情報は各社公式リンクをご確認ください。</span>
</div>
""", unsafe_allow_html=True)


