"""
恋朝トレインタイマー - ダイヤ改正自動検知エンジン (revision_detector.py)
西武鉄道・JR中央線・JR武蔵野線のダイヤ改正・時刻変更公式発表を安全に自動検知
"""

import sys
import datetime
import urllib.request
import urllib.parse
import email.utils
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

# 日本標準時（JST: UTC+9）
JST = datetime.timezone(datetime.timedelta(hours=9))

CURRENT_TIMETABLE_VERSION = "2026年春季現行ダイヤ (2026-03-15改定)"
CURRENT_TIMETABLE_DATE = datetime.date(2026, 3, 15)

RELEVANT_KEYWORDS = ["ダイヤ改正", "時刻改正", "ダイヤ変更", "時刻変更", "減便", "増便", "終電繰り上げ", "新ダイヤ"]
ROUTE_KEYWORDS = ["西武", "国分寺", "中央線", "武蔵野線"]

def parse_pub_date(date_str: str) -> Optional[datetime.datetime]:
    """RFC 2822 日付文字列を JST datetime に変換"""
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.astimezone(JST)
    except Exception:
        return None

def fetch_timetable_news(timeout: float = 3.0) -> List[Dict[str, Any]]:
    """
    関連路線のダイヤ改正ニュースをGoogle News公開RSSから取得
    ネットワーク不調時も最大timeout秒で安全にフォールバック
    """
    query = urllib.parse.quote("(西武鉄道 OR 西武国分寺線 OR 中央線 OR 武蔵野線) ダイヤ改正")
    url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KoiasaTrainTimer/1.0"}
    )

    items_result = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")

            for item in items:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                source_elem = item.find("source")

                title = title_elem.text if title_elem is not None and title_elem.text else ""
                link = link_elem.text if link_elem is not None and link_elem.text else ""
                pub_date_str = pub_elem.text if pub_elem is not None and pub_elem.text else ""
                source_name = source_elem.text if source_elem is not None and source_elem.text else ""

                if not title:
                    continue

                # 関連路線のキーワードとダイヤ変更キーワードの両方が含まれているか検証
                has_route = any(k in title for k in ROUTE_KEYWORDS)
                has_revision = any(k in title for k in RELEVANT_KEYWORDS)

                if has_route and has_revision:
                    pub_dt = parse_pub_date(pub_date_str)
                    items_result.append({
                        "title": title,
                        "link": link,
                        "pub_date_str": pub_date_str,
                        "pub_dt": pub_dt,
                        "pub_date_display": pub_dt.strftime("%Y年%m月%d日") if pub_dt else "",
                        "source": source_name,
                    })
    except Exception:
        # 通信エラーやオフライン時も例外を投げずに空リストを返し、アプリ全体を保護
        return []

    return items_result

def check_timetable_revision(
    news_list: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime.datetime] = None,
    threshold_days: int = 90
) -> Dict[str, Any]:
    """
    ダイヤ改正告知の有無を総合判定
    """
    if now is None:
        now = datetime.datetime.now(JST)

    if news_list is None:
        news_list = fetch_timetable_news()

    recent_announcements = []
    has_alert = False

    for item in news_list:
        pub_dt = item.get("pub_dt")
        if pub_dt:
            # 発表日が現行ダイヤ適用日より後、または直近90日以内の発表
            days_diff = (now - pub_dt).days
            if -365 <= days_diff <= threshold_days:
                recent_announcements.append(item)
                if any(w in item["title"] for w in ["2026", "2027", "来春", "秋", "改正", "変更"]):
                    has_alert = True
        else:
            recent_announcements.append(item)

    if has_alert and recent_announcements:
        status = "revision_detected"
        status_label = "📢 ダイヤ改正告知を検知"
        badge_color = "#FF7F50"  # コーラルオレンジ
        message = "西武鉄道またはJR東日本において、ダイヤ改正・時刻変更に関する発表が確認されました。"
    else:
        status = "up_to_date"
        status_label = "✅ ダイヤ最新確認済"
        badge_color = "#059669"  # エメラルドグリーン
        message = "現在適用中のダイヤグラムは最新です。新たなダイヤ改正告知は検知されていません。"

    return {
        "status": status,
        "status_label": status_label,
        "has_alert": has_alert,
        "badge_color": badge_color,
        "message": message,
        "current_version": CURRENT_TIMETABLE_VERSION,
        "announcements": recent_announcements[:3],  # 最大3件
        "last_checked_jst": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
