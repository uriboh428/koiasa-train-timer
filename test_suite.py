"""
恋朝トレインタイマー 包括的自動テストスイート
ダイヤ計算ロジック、乗換接続整合性、セキュリティサニタイズの全件検証
"""

import unittest
import datetime
from timetable_data import (
    KOIGAKUBO_DEPARTURES,
    KOKUBUNJI_CHUO_DOWN,
    NISHI_KOKUBUNJI_MUSASHINO_UP,
    KITA_ASAKADAI_MUSASHINO_DOWN,
    LINE_INFO,
)
from transit_engine import (
    find_next_departure,
    find_next_departures_list,
    get_transfer_buffer,
    calculate_koigakubo_to_asakadai,
    calculate_asakadai_to_koigakubo,
    get_routes,
    get_last_train_info,
    escape_text,
    is_safe_url,
)

class TestTransitEngine(unittest.TestCase):

    def test_timetables_exist(self):
        """全路線のダイヤデータが存在し、主要時間帯が網羅されているか"""
        self.assertIn(7, KOIGAKUBO_DEPARTURES)
        self.assertIn(12, KOIGAKUBO_DEPARTURES)
        self.assertIn(18, KOIGAKUBO_DEPARTURES)
        self.assertGreater(len(KOKUBUNJI_CHUO_DOWN[8]), 5)
        self.assertGreater(len(NISHI_KOKUBUNJI_MUSASHINO_UP[8]), 4)
        self.assertGreater(len(KITA_ASAKADAI_MUSASHINO_DOWN[8]), 4)

    def test_find_next_departure_exact(self):
        """指定時刻から正しい直近発車時刻を取得できるか"""
        base = datetime.datetime(2026, 9, 20, 8, 0, 0)
        # 8:00 以降の恋ヶ窪発（8:02のはず）
        nxt = find_next_departure(KOIGAKUBO_DEPARTURES, base)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.hour, 8)
        self.assertEqual(nxt.minute, 2)

    def test_find_next_departure_daytime(self):
        """日中時間帯の次発取得"""
        base = datetime.datetime(2026, 9, 20, 12, 10, 0)
        nxt = find_next_departure(KOIGAKUBO_DEPARTURES, base)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.hour, 12)
        self.assertEqual(nxt.minute, 15)

    def test_find_next_departures_list(self):
        """直近3便が正しく時間順に取得できるか"""
        base = datetime.datetime(2026, 9, 20, 10, 0, 0)
        depts = find_next_departures_list(KOIGAKUBO_DEPARTURES, base, 3)
        self.assertEqual(len(depts), 3)
        self.assertTrue(depts[0] < depts[1] < depts[2])

    def test_transfer_buffer(self):
        """乗換ペースに応じた所要時間バッファ"""
        self.assertEqual(get_transfer_buffer("kokubunji", "fast"), 2)
        self.assertEqual(get_transfer_buffer("kokubunji", "normal"), 3)
        self.assertEqual(get_transfer_buffer("kokubunji", "relaxed"), 5)
        self.assertEqual(get_transfer_buffer("nishi_kokubunji", "fast"), 3)
        self.assertEqual(get_transfer_buffer("nishi_kokubunji", "normal"), 4)
        self.assertEqual(get_transfer_buffer("nishi_kokubunji", "relaxed"), 6)

    def test_calculate_koigakubo_to_asakadai(self):
        """往路：恋ヶ窪 ➡ 朝霞台 の全行程計算整合性"""
        dept = datetime.datetime(2026, 9, 20, 8, 10, 0)
        now = datetime.datetime(2026, 9, 20, 8, 5, 0)
        result = calculate_koigakubo_to_asakadai(dept, "normal", now)

        self.assertEqual(result["direction"], "koigakubo_to_asakadai")
        self.assertEqual(result["departure_time"], "08:10")
        self.assertEqual(len(result["legs"]), 3)
        self.assertGreaterEqual(result["total_minutes"], 30)
        self.assertLessEqual(result["total_minutes"], 50)
        self.assertEqual(result["seconds_until_departure"], 300)

    def test_calculate_asakadai_to_koigakubo(self):
        """復路：朝霞台 ➡ 恋ヶ窪 の全行程計算整合性"""
        dept = datetime.datetime(2026, 9, 20, 17, 17, 0)
        now = datetime.datetime(2026, 9, 20, 17, 10, 0)
        result = calculate_asakadai_to_koigakubo(dept, "normal", now)

        self.assertEqual(result["direction"], "asakadai_to_koigakubo")
        self.assertEqual(result["departure_time"], "17:17")
        self.assertEqual(len(result["legs"]), 3)
        self.assertGreaterEqual(result["total_minutes"], 30)
        self.assertLessEqual(result["total_minutes"], 50)
        self.assertEqual(result["seconds_until_departure"], 420)

    def test_get_routes(self):
        """get_routes関数が複数便を正しく生成するか"""
        now = datetime.datetime(2026, 9, 20, 9, 0, 0)
        routes_k2a = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=now)
        self.assertGreaterEqual(len(routes_k2a), 1)

        routes_a2k = get_routes("asakadai_to_koigakubo", offset_minutes=10, pace="fast", now=now)
        self.assertGreaterEqual(len(routes_a2k), 1)

    def test_security_escape_text(self):
        """XSS対策サニタイズテスト"""
        malicious = '<script>alert("XSS")</script>'
        safe = escape_text(malicious)
        self.assertNotIn('<script>', safe)
        self.assertIn('&lt;script&gt;', safe)

    def test_security_is_safe_url(self):
        """安全なURL検証テスト（javascript:等のインジェクション遮断）"""
        self.assertTrue(is_safe_url("https://www.jreast.co.jp"))
        self.assertTrue(is_safe_url("http://localhost:8501"))
        self.assertFalse(is_safe_url("javascript:alert(1)"))
        self.assertFalse(is_safe_url("data:text/html,..."))
        self.assertFalse(is_safe_url(""))

    def test_last_train_koigakubo_to_asakadai(self):
        """恋ヶ窪 ➡ 朝霞台 終電ナビゲーションの判定テスト"""
        # 夜21:00のケース
        now_21 = datetime.datetime(2026, 9, 20, 21, 0, 0)
        info_21 = get_last_train_info("koigakubo_to_asakadai", now=now_21)
        self.assertEqual(info_21["departure_time"], "00:03")
        self.assertEqual(info_21["arrival_time"], "00:45")
        self.assertFalse(info_21["is_expired"])
        self.assertEqual(info_21["seconds_until_last_train"], 3 * 3600 + 3 * 60)

        # 深夜0:01のケース（あと2分）
        now_0001 = datetime.datetime(2026, 9, 21, 0, 1, 0)
        info_0001 = get_last_train_info("koigakubo_to_asakadai", now=now_0001)
        self.assertFalse(info_0001["is_expired"])
        self.assertEqual(info_0001["seconds_until_last_train"], 120)

        # 深夜1:00のケース（運行終了）
        now_0100 = datetime.datetime(2026, 9, 21, 1, 0, 0)
        info_0100 = get_last_train_info("koigakubo_to_asakadai", now=now_0100)
        self.assertTrue(info_0100["is_expired"])
        self.assertEqual(info_0100["seconds_until_last_train"], 0)

    def test_last_train_asakadai_to_koigakubo(self):
        """朝霞台 ➡ 恋ヶ窪 終電ナビゲーションの判定テスト"""
        # 夜21:00のケース
        now_21 = datetime.datetime(2026, 9, 20, 21, 0, 0)
        info_21 = get_last_train_info("asakadai_to_koigakubo", now=now_21)
        self.assertEqual(info_21["departure_time"], "23:45")
        self.assertEqual(info_21["arrival_time"], "00:34")
        self.assertFalse(info_21["is_expired"])
        self.assertEqual(info_21["seconds_until_last_train"], 2 * 3600 + 45 * 60)

        # 夜23:50のケース（運行終了）
        now_2350 = datetime.datetime(2026, 9, 20, 23, 50, 0)
        info_2350 = get_last_train_info("asakadai_to_koigakubo", now=now_2350)
        self.assertTrue(info_2350["is_expired"])
        self.assertEqual(info_2350["seconds_until_last_train"], 0)

if __name__ == '__main__':
    unittest.main()

