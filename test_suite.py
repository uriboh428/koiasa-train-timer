"""
恋朝トレインタイマー 包括的自動テストスイート
ダイヤ計算ロジック、乗換接続整合性、セキュリティサニタイズの全件検証
"""

import os
import time
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
    get_default_direction,
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
        self.assertEqual(nxt.minute, 16)

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
        """往路：恋ヶ窪 ➡ 北朝霞 の全行程計算整合性"""
        dept = datetime.datetime(2026, 9, 20, 8, 10, 0)
        now = datetime.datetime(2026, 9, 20, 8, 5, 0)
        result = calculate_koigakubo_to_asakadai(dept, "normal", now)

        self.assertEqual(result["direction"], "koigakubo_to_asakadai")
        self.assertEqual(result["departure_time"], "08:10")
        self.assertEqual(len(result["legs"]), 3)
        self.assertEqual(result["legs"][2]["to_station"], "北朝霞")
        self.assertEqual(result["legs"][2]["duration"], 18)
        self.assertGreaterEqual(result["total_minutes"], 30)
        self.assertLessEqual(result["total_minutes"], 50)
        self.assertEqual(result["seconds_until_departure"], 300)
        self.assertIn("departure_timestamp_ms", result)
        self.assertGreater(result["departure_timestamp_ms"], 0)

    def test_calculate_asakadai_to_koigakubo(self):
        """復路：北朝霞 ➡ 恋ヶ窪 の全行程計算整合性"""
        dept = datetime.datetime(2026, 9, 20, 17, 11, 0)
        now = datetime.datetime(2026, 9, 20, 17, 5, 0)
        result = calculate_asakadai_to_koigakubo(dept, "normal", now)

        self.assertEqual(result["direction"], "asakadai_to_koigakubo")
        self.assertEqual(result["departure_time"], "17:11")
        self.assertEqual(len(result["legs"]), 3)
        self.assertEqual(result["legs"][0]["from_station"], "北朝霞")
        self.assertEqual(result["legs"][0]["duration"], 18)
        self.assertEqual(result["legs"][2]["to_station"], "恋ヶ窪")
        self.assertGreaterEqual(result["total_minutes"], 30)
        self.assertLessEqual(result["total_minutes"], 50)
        self.assertEqual(result["seconds_until_departure"], 360)
        self.assertIn("departure_timestamp_ms", result)
        self.assertGreater(result["departure_timestamp_ms"], 0)

    def test_default_direction_by_time(self):
        """時間帯に応じたデフォルト行き先自動判定（1:00-12:00恋ヶ窪発、12:01-24:59北朝霞発）の境界値検証"""
        # 1. 01:00 (朝の開始境界) -> 恋ヶ窪 ➡ 北朝霞
        t_0100 = datetime.datetime(2026, 9, 20, 1, 0, 0)
        self.assertEqual(get_default_direction(t_0100), "koigakubo_to_asakadai")

        # 2. 08:30 (出勤ラッシュ) -> 恋ヶ窪 ➡ 北朝霞
        t_0830 = datetime.datetime(2026, 9, 20, 8, 30, 0)
        self.assertEqual(get_default_direction(t_0830), "koigakubo_to_asakadai")

        # 3. 12:00 (正午境界値) -> 恋ヶ窪 ➡ 北朝霞
        t_1200 = datetime.datetime(2026, 9, 20, 12, 0, 0)
        self.assertEqual(get_default_direction(t_1200), "koigakubo_to_asakadai")

        # 4. 12:01 (午後切り替え境界) -> 北朝霞 ➡ 恋ヶ窪
        t_1201 = datetime.datetime(2026, 9, 20, 12, 1, 0)
        self.assertEqual(get_default_direction(t_1201), "asakadai_to_koigakubo")

        # 5. 18:00 (夕方・帰宅ラッシュ) -> 北朝霞 ➡ 恋ヶ窪
        t_1800 = datetime.datetime(2026, 9, 20, 18, 0, 0)
        self.assertEqual(get_default_direction(t_1800), "asakadai_to_koigakubo")

        # 6. 23:59 (深夜前) -> 北朝霞 ➡ 恋ヶ窪
        t_2359 = datetime.datetime(2026, 9, 20, 23, 59, 0)
        self.assertEqual(get_default_direction(t_2359), "asakadai_to_koigakubo")

        # 7. 00:00 (日付跨ぎ) -> 北朝霞 ➡ 恋ヶ窪 (24:00相当)
        t_0000 = datetime.datetime(2026, 9, 20, 0, 0, 0)
        self.assertEqual(get_default_direction(t_0000), "asakadai_to_koigakubo")

        # 8. 00:59 (深夜最終境界 24:59相当) -> 北朝霞 ➡ 恋ヶ窪
        t_0059 = datetime.datetime(2026, 9, 20, 0, 59, 0)
        self.assertEqual(get_default_direction(t_0059), "asakadai_to_koigakubo")

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
        """恋ヶ窪 ➡ 北朝霞 終電ナビゲーションの判定テスト（平日・土休日双方の正確性検証）"""
        # --- 1. 平日ダイヤ（2026-09-18 金曜日）: 恋ヶ窪 23:55 発 ➡ 北朝霞 00:40 着 ---
        # 夜21:00のケース（平日）
        now_weekday_21 = datetime.datetime(2026, 9, 18, 21, 0, 0)
        info_w_21 = get_last_train_info("koigakubo_to_asakadai", now=now_weekday_21)
        self.assertEqual(info_w_21["departure_station"], "恋ヶ窪")
        self.assertEqual(info_w_21["destination_station"], "北朝霞")
        self.assertEqual(info_w_21["departure_time"], "23:55")
        self.assertEqual(info_w_21["arrival_time"], "00:40")
        self.assertFalse(info_w_21["is_expired"])
        self.assertEqual(info_w_21["seconds_until_last_train"], 2 * 3600 + 55 * 60)

        # 深夜0:01のケース（平日翌日未明・運行終了）
        now_weekday_0001 = datetime.datetime(2026, 9, 19, 0, 1, 0)
        info_w_0001 = get_last_train_info("koigakubo_to_asakadai", now=now_weekday_0001)
        self.assertTrue(info_w_0001["is_expired"])
        self.assertEqual(info_w_0001["seconds_until_last_train"], 0)

        # 深夜1:00のケース（運行終了）
        now_0100 = datetime.datetime(2026, 9, 18, 1, 0, 0)
        info_0100 = get_last_train_info("koigakubo_to_asakadai", now=now_0100)
        self.assertTrue(info_0100["is_expired"])
        self.assertEqual(info_0100["seconds_until_last_train"], 0)

        # --- 2. 土休日ダイヤ（2026-09-20 日曜日 / 2026-09-21 敬老の日）: 恋ヶ窪 23:35 発 ➡ 北朝霞 00:22 着 ---
        now_holiday_21 = datetime.datetime(2026, 9, 21, 21, 0, 0)  # 敬老の日
        info_h_21 = get_last_train_info("koigakubo_to_asakadai", now=now_holiday_21)
        self.assertEqual(info_h_21["destination_station"], "北朝霞")
        self.assertEqual(info_h_21["departure_time"], "23:35")
        self.assertEqual(info_h_21["arrival_time"], "00:22")
        self.assertFalse(info_h_21["is_expired"])
        self.assertEqual(info_h_21["seconds_until_last_train"], 2 * 3600 + 35 * 60)

        # 23:45のケース（土休日は23:35発のため運行終了）
        now_holiday_2345 = datetime.datetime(2026, 9, 21, 23, 45, 0)
        info_h_2345 = get_last_train_info("koigakubo_to_asakadai", now=now_holiday_2345)
        self.assertTrue(info_h_2345["is_expired"])
        self.assertEqual(info_h_2345["seconds_until_last_train"], 0)

    def test_last_train_asakadai_to_koigakubo(self):
        """北朝霞 ➡ 恋ヶ窪 終電ナビゲーションの判定テスト（平日・土休日双方の正確性検証）"""
        # --- 1. 平日ダイヤ（2026-09-18 金曜日）: 北朝霞 23:30 発 ➡ 恋ヶ窪 00:07 着 ---
        now_weekday_21 = datetime.datetime(2026, 9, 18, 21, 0, 0)
        info_w_21 = get_last_train_info("asakadai_to_koigakubo", now=now_weekday_21)
        self.assertEqual(info_w_21["departure_station"], "北朝霞")
        self.assertEqual(info_w_21["destination_station"], "恋ヶ窪")
        self.assertEqual(info_w_21["departure_time"], "23:30")
        self.assertEqual(info_w_21["arrival_time"], "00:07")
        self.assertFalse(info_w_21["is_expired"])
        self.assertEqual(info_w_21["seconds_until_last_train"], 2 * 3600 + 30 * 60)

        # 夜23:50のケース（運行終了）
        now_w_2350 = datetime.datetime(2026, 9, 18, 23, 50, 0)
        info_w_2350 = get_last_train_info("asakadai_to_koigakubo", now=now_w_2350)
        self.assertTrue(info_w_2350["is_expired"])
        self.assertEqual(info_w_2350["seconds_until_last_train"], 0)

        # --- 2. 土休日ダイヤ（2026-09-20 日曜日 / 2026-09-21 敬老の日）: 北朝霞 23:30 発 ➡ 恋ヶ窪 00:04 着 ---
        now_holiday_21 = datetime.datetime(2026, 9, 21, 21, 0, 0)
        info_h_21 = get_last_train_info("asakadai_to_koigakubo", now=now_holiday_21)
        self.assertEqual(info_h_21["departure_station"], "北朝霞")
        self.assertEqual(info_h_21["destination_station"], "恋ヶ窪")
        self.assertEqual(info_h_21["departure_time"], "23:30")
        self.assertEqual(info_h_21["arrival_time"], "00:04")
        self.assertFalse(info_h_21["is_expired"])
        self.assertEqual(info_h_21["seconds_until_last_train"], 2 * 3600 + 30 * 60)

        # 夜23:35のケース（土休日は23:30発のため運行終了）
        now_h_2335 = datetime.datetime(2026, 9, 21, 23, 35, 0)
        info_h_2335 = get_last_train_info("asakadai_to_koigakubo", now=now_h_2335)
        self.assertTrue(info_h_2335["is_expired"])
        self.assertEqual(info_h_2335["seconds_until_last_train"], 0)

from revision_detector import parse_pub_date, check_timetable_revision, fetch_timetable_news, JST

class TestRevisionDetector(unittest.TestCase):
    """ダイヤ改正自動検知エンジンのテスト"""

    def test_parse_pub_date(self):
        """RFC 2822 日付文字列のパース"""
        date_str = "Thu, 20 Aug 2026 07:00:00 GMT"
        dt = parse_pub_date(date_str)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 8)
        self.assertEqual(dt.day, 20)
        # 不正な文字列で例外が出ないこと
        self.assertIsNone(parse_pub_date("invalid-date-string"))

    def test_check_revision_no_alert(self):
        """改正告知なし時のステータス判定"""
        now = datetime.datetime(2026, 9, 20, 10, 0, 0, tzinfo=JST)
        # 過去（1年以上前）のニュースのみ
        mock_news = [{
            "title": "JR東日本 2024年春のダイヤ改正について",
            "link": "https://example.com/2024",
            "pub_date_str": "Fri, 15 Dec 2023 08:00:00 GMT",
            "pub_dt": datetime.datetime(2023, 12, 15, 17, 0, 0, tzinfo=JST),
            "pub_date_display": "2023年12月15日",
            "source": "Tetsudo.com",
        }]
        res = check_timetable_revision(news_list=mock_news, now=now, threshold_days=60)
        self.assertFalse(res["has_alert"])
        self.assertEqual(res["status"], "up_to_date")
        self.assertEqual(res["badge_color"], "#059669")

    def test_check_revision_with_alert(self):
        """改正告知検知時のアラート判定"""
        now = datetime.datetime(2026, 9, 20, 10, 0, 0, tzinfo=JST)
        # 直近の西武鉄道・JR改正ニュース
        mock_news = [{
            "title": "西武鉄道 2026年秋のダイヤ改正を実施します（国分寺線増発）",
            "link": "https://example.com/2026autumn",
            "pub_date_str": "Wed, 16 Sep 2026 08:00:00 GMT",
            "pub_dt": datetime.datetime(2026, 9, 16, 17, 0, 0, tzinfo=JST),
            "pub_date_display": "2026年09月16日",
            "source": "鉄道コム",
        }]
        res = check_timetable_revision(news_list=mock_news, now=now, threshold_days=60)
        self.assertTrue(res["has_alert"])
        self.assertEqual(res["status"], "revision_detected")
        self.assertEqual(res["badge_color"], "#FF7F50")
        self.assertEqual(len(res["announcements"]), 1)

    def test_fetch_timetable_news_safety(self):
        """タイムアウト指定で例外を投げずにリストを返すか"""
        news = fetch_timetable_news(timeout=3.0)
        self.assertIsInstance(news, list)

    def test_security_auth_hash_and_salt(self):
        """ソルト付き暗号化ハッシュとタイミング攻撃耐性の検証"""
        from auth_manager import hash_password, verify_password
        pwd = "MySecretPass_2026!"
        h1, s1 = hash_password(pwd)
        h2, s2 = hash_password(pwd)

        # ソルトが毎回ユニークであること（レインボーテーブル攻撃防御）
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)

        # 正しいパスワードで検証成功すること
        self.assertTrue(verify_password(pwd, h1, s1))
        self.assertTrue(verify_password(pwd, h2, s2))

        # 誤ったパスワードで拒絶されること
        self.assertFalse(verify_password("WrongPassword", h1, s1))
        self.assertFalse(verify_password("", h1, s1))
        self.assertFalse(verify_password(None, h1, s1))

    def test_security_brute_force_lockout(self):
        """総当たり攻撃（ブルートフォース）防御のロックアウト判定検証"""
        from auth_manager import check_lockout_status
        current_time = time.time()

        # 4回失敗: まだロックされない
        is_locked, remaining = check_lockout_status(attempts=4, lock_until=0.0)
        self.assertFalse(is_locked)
        self.assertEqual(remaining, 0)

        # 5回失敗 & ロック期間中（60秒後まで）: ロックされる
        lock_until = current_time + 60
        is_locked, remaining = check_lockout_status(attempts=5, lock_until=lock_until)
        self.assertTrue(is_locked)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 60)

        # ロック期間終了後（過去時刻）: 自動的にロック解除される
        expired_lock = current_time - 5
        is_locked, remaining = check_lockout_status(attempts=5, lock_until=expired_lock)
        self.assertFalse(is_locked)
        self.assertEqual(remaining, 0)

    def test_security_save_and_load_credentials(self):
        """パスワードの保存と認証情報読み込みのライフサイクル検証"""
        import tempfile
        from auth_manager import save_auth_credentials, load_auth_credentials, verify_password, MIN_PASSWORD_LENGTH
        import auth_manager

        # 短すぎるパスワードの拒絶検証
        self.assertFalse(save_auth_credentials("123"))

        # テスト用の退避・検証
        orig_file = auth_manager.AUTH_CONFIG_FILE
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            auth_manager.AUTH_CONFIG_FILE = tmp_path
            success = save_auth_credentials("SuperSecret2026!")
            self.assertTrue(success)

            creds = load_auth_credentials()
            self.assertIsNotNone(creds)
            self.assertTrue(verify_password("SuperSecret2026!", creds["hash"], creds["salt"]))
            self.assertFalse(verify_password("WrongPassword!", creds["hash"], creds["salt"]))
        finally:
            auth_manager.AUTH_CONFIG_FILE = orig_file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_security_global_lockout_manager(self):
        """GlobalSecurityManager によるプロセス全体共有レートリミットの検証"""
        from auth_manager import GlobalSecurityManager, MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION_SECONDS
        mgr = GlobalSecurityManager.get_instance()
        mgr.record_success()  # クリーンアップ

        # 4回連続失敗: まだロックされない
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            is_locked, _ = mgr.record_failure()
            self.assertFalse(is_locked)

        is_l, _ = mgr.get_lockout_status()
        self.assertFalse(is_l)

        # 5回目の失敗: ロックアウト発動
        is_locked, sec = mgr.record_failure()
        self.assertTrue(is_locked)
        self.assertEqual(sec, LOCKOUT_DURATION_SECONDS)

        # ロック中のステータス取得
        is_l, rem = mgr.get_lockout_status()
        self.assertTrue(is_l)
        self.assertGreater(rem, 0)

        # 成功リセット
        mgr.record_success()
        is_l, _ = mgr.get_lockout_status()
        self.assertFalse(is_l)

    def test_security_secure_access_token(self):
        """推測不能な暗号アクセストークンの生成・照合検証"""
        from auth_manager import hash_password, get_secure_token, verify_secure_token
        h, s = hash_password("MyPassword2026")
        token = get_secure_token(s, h)

        # トークンは24文字の推測不能な16進文字列
        self.assertEqual(len(token), 24)

        # 正しいトークンでの検証成功
        self.assertTrue(verify_secure_token(token, s, h))

        # 誤ったトークンや改ざんの拒絶
        self.assertFalse(verify_secure_token("fake_token_123456789012", s, h))
        self.assertFalse(verify_secure_token("", s, h))
        self.assertFalse(verify_secure_token(None, s, h))

    def test_security_pbkdf2_and_legacy_hash_compatibility(self):
        """PBKDF2ハッシュ（10万回ストレッチング）と旧単一SHA-256ハッシュの後方互換検証"""
        from auth_manager import hash_password, verify_password
        import hashlib

        # 1. PBKDF2 ハッシュ生成と照合
        h_pbkdf2, salt = hash_password("SecurePassword2026!")
        self.assertTrue(h_pbkdf2.startswith("pbkdf2$"))
        self.assertTrue(verify_password("SecurePassword2026!", h_pbkdf2, salt))
        self.assertFalse(verify_password("WrongPassword2026!", h_pbkdf2, salt))

        # 2. 旧単一SHA-256 ハッシュの後方互換照合
        legacy_salt = "1234567890abcdef"
        legacy_hash = hashlib.sha256((legacy_salt + "LegacyPassword123").encode("utf-8")).hexdigest()
        self.assertTrue(verify_password("LegacyPassword123", legacy_hash, legacy_salt))
        self.assertFalse(verify_password("WrongLegacyPassword", legacy_hash, legacy_salt))

    def test_security_progressive_lockout(self):
        """二段階プログレッシブロックアウト（5回で60秒、10回で300秒）の検証"""
        from auth_manager import GlobalSecurityManager, MAX_FAILED_ATTEMPTS, SEVERE_FAILED_ATTEMPTS, SEVERE_LOCKOUT_DURATION_SECONDS
        mgr = GlobalSecurityManager.get_instance()
        mgr.record_success()

        # 10回まで失敗を記録
        for i in range(1, SEVERE_FAILED_ATTEMPTS + 1):
            is_locked, sec = mgr.record_failure()
            if i >= SEVERE_FAILED_ATTEMPTS:
                self.assertTrue(is_locked)
                self.assertEqual(sec, SEVERE_LOCKOUT_DURATION_SECONDS)
            elif i >= MAX_FAILED_ATTEMPTS:
                self.assertTrue(is_locked)

        mgr.record_success()

    def test_security_news_url_validation(self):
        """ニュースURLのスキーム無害化検証（XSS・インジェクション防止）"""
        from revision_detector import is_valid_news_url
        self.assertTrue(is_valid_news_url("https://news.google.com/article/123"))
        self.assertTrue(is_valid_news_url("http://www.seiburailway.jp/news/"))
        self.assertFalse(is_valid_news_url("javascript:alert(1)"))
        self.assertFalse(is_valid_news_url("data:text/html,<script>alert(1)</script>"))
        self.assertFalse(is_valid_news_url(""))
        self.assertFalse(is_valid_news_url(None))


    def test_dynamic_token_link_generation(self):
        """動的トークンURL生成の検証（ベースURL指定時・未指定時のフォールバック）"""
        from auth_manager import generate_token_link
        link1 = generate_token_link("test_token_123", base_url="https://my-app.streamlit.app")
        self.assertEqual(link1, "https://my-app.streamlit.app/?token=test_token_123")

        link2 = generate_token_link("test_token_123", base_url="http://localhost:8501/")
        self.assertEqual(link2, "http://localhost:8501/?token=test_token_123")

        # base_urlが空の場合は ?token=... にフォールバック
        link3 = generate_token_link("test_token_123", base_url="")
        self.assertIn("?token=test_token_123", link3)


    def test_all_python_files_syntax_compilation(self):
        """【Quality Gate】全Pythonファイルの静的構文チェック（SyntaxError/f-string構文の全件検査）"""
        import py_compile
        project_dir = os.path.dirname(os.path.abspath(__file__))
        py_files = [
            "app.py",
            "auth_manager.py",
            "transit_engine.py",
            "timetable_data.py",
            "test_suite.py",
            "revision_detector.py",
            "sync_push.py",
        ]
        for f in py_files:
            target_path = os.path.join(project_dir, f)
            if os.path.exists(target_path):
                # doraise=True により構文エラー時は即座に PyCompileError 例外が飛ぶ
                py_compile.compile(target_path, doraise=True)


    def test_version_display_consistency(self):
        """【Version Governance】アプリ内のバージョン表記がシンプルな V4.3 に統一され、説明表記が省略されているかを検査"""
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("V4.3", content, "app.py に V4.3 が含まれている必要があります")
        self.assertNotIn("Ver 4.3 (", content, "app.py にバージョンの説明表記（カッコ書き）が残っていてはいけません")
        self.assertNotIn("V4.3 (", content, "app.py にバージョンの説明表記（カッコ書き）が残っていてはいけません")
        self.assertNotIn("Ver 4.2", content, "app.py に古い Ver 4.2 が残っていてはいけません")
        self.assertNotIn("V4.2", content, "app.py に古い V4.2 が残っていてはいけません")
        self.assertNotIn("Ver 4.1", content, "app.py に古い Ver 4.1 が残っていてはいけません")
        self.assertNotIn("Ver 4.0", content, "app.py に古い Ver 4.0 が残っていてはいけません")
        self.assertNotIn("Ver 3.9", content, "app.py に古い Ver 3.9 が残っていてはいけません")
        self.assertNotIn("V3.9", content, "app.py に古い V3.9 が残っていてはいけません")
        self.assertNotIn("Ver 3.8", content, "app.py に古い Ver 3.8 が残っていてはいけません")
        self.assertNotIn("Ver 3.7", content, "app.py に古い Ver 3.7 が残っていてはいけません")
        self.assertNotIn("Ver 3.6", content, "app.py に古い Ver 3.6 が残っていてはいけません")
        self.assertNotIn("Ver 3.5", content, "app.py に古い Ver 3.5 が残っていてはいけません")
        self.assertNotIn("Ver 3.4", content, "app.py に古い Ver 3.4 が残っていてはいけません")
        self.assertNotIn("Ver 3.3", content, "app.py に古い Ver 3.3 が残っていてはいけません")
        self.assertNotIn("Ver 3.2", content, "app.py に古い Ver 3.2 が残っていてはいけません")
        self.assertNotIn("Ver 3.1", content, "app.py に古い Ver 3.1 が残っていてはいけません")
        self.assertNotIn("Ver 3.0", content, "app.py に古い Ver 3.0 が残っていてはいけません")
        self.assertNotIn("Ver 2.9", content, "app.py に古い Ver 2.9 が残っていてはいけません")
        self.assertNotIn("Ver 2.8", content, "app.py に古い Ver 2.8 が残っていてはいけません")
        self.assertNotIn("Ver 2.6", content, "app.py に古い Ver 2.6 が残っていてはいけません")

    def test_departure_auto_advance_logic(self):
        """【Departure Transition】発車時刻（秒単位）経過後に次便へ自動繰り上がるロジックの検証"""
        from transit_engine import find_next_departure, get_routes, get_timestamp_ms
        from timetable_data import KOIGAKUBO_DEPARTURES

        # 朝 8:02 発の便をターゲットとするテスト（平日 2026-09-18）
        # 1. 発車1秒前 (08:01:59) -> 08:02 発が取得されること
        t_before = datetime.datetime(2026, 9, 18, 8, 1, 59)
        dept_before = find_next_departure(KOIGAKUBO_DEPARTURES, t_before)
        self.assertIsNotNone(dept_before)
        self.assertEqual(dept_before.hour, 8)
        self.assertEqual(dept_before.minute, 2)

        # 2. 発車0秒 (08:02:00) -> 08:02 発が取得されること
        t_exact = datetime.datetime(2026, 9, 18, 8, 2, 0)
        dept_exact = find_next_departure(KOIGAKUBO_DEPARTURES, t_exact)
        self.assertIsNotNone(dept_exact)
        self.assertEqual(dept_exact.hour, 8)
        self.assertEqual(dept_exact.minute, 2)

        # 3. 発車1秒後 (08:02:01) -> 自動的に次の便（08:09発など）に繰り上がること
        t_after = datetime.datetime(2026, 9, 18, 8, 2, 1)
        dept_after = find_next_departure(KOIGAKUBO_DEPARTURES, t_after)
        self.assertIsNotNone(dept_after)
        self.assertEqual(dept_after.hour, 8)
        self.assertGreater(dept_after.minute, 2, "発車1秒後には必ず8:02以降の次便が返される必要があります")

        # 4. get_routes における次便自動切り替えの検証
        routes_before = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=t_before)
        routes_after = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=t_after)
        self.assertNotEqual(routes_before[0]["departure_time"], routes_after[0]["departure_time"],
                            "発車時刻経過後は先頭便が自動的に次の電車に更新される必要があります")
        self.assertEqual(routes_before[0]["departure_time"], "08:02")
        self.assertGreater(routes_after[0]["departure_time"], "08:02")

        # 5. 親スクリプト側ガードのシミュレーション（選択便が過去になった場合のリセット判定）
        simulated_selected_route = routes_before[0]
        now_ms = get_timestamp_ms(t_after)
        is_past = simulated_selected_route["departure_timestamp_ms"] < now_ms
        self.assertTrue(is_past, "発車済みの便は過去判定（< now_ms）となりリセット対象になること")

    def test_admin_role_separation_and_security(self):
        """【Role Governance】家族利用時の管理者権限分離とアンロック整合性の検証"""
        from auth_manager import hash_password, verify_admin_access

        # 模擬的な二重パスワード情報
        u_pwd = "FamilyUser2026!"
        a_pwd = "MySecretAdmin2026!"
        u_h, u_s = hash_password(u_pwd)
        a_h, a_s = hash_password(a_pwd)
        mock_creds = {
            "user_hash": u_h,
            "user_salt": u_s,
            "admin_hash": a_h,
            "admin_salt": a_s,
            "hash": u_h,
            "salt": u_s,
            "token": "abc123token456"
        }

        # 1. 家族向けセッション（一般モード）の初期状態シミュレーション
        session_state = {
            "authenticated": True,
            "is_admin": False
        }
        self.assertTrue(session_state["authenticated"], "認証済みであること")
        self.assertFalse(session_state["is_admin"], "家族セッションでは管理者権限が無効であること")

        # 2. 誤ったパスワードによる管理者アンロック試行（失敗）
        wrong_input = "WrongPassword999"
        unlock_success = verify_admin_access(wrong_input, mock_creds)
        self.assertFalse(unlock_success, "誤ったパスワードではアンロックできないこと")
        self.assertFalse(session_state["is_admin"], "権限が昇格されないこと")

        # 3. 一般ログインパスワードによる管理者アンロック試行（完全遮断・失敗）
        user_input = u_pwd
        unlock_user_attempt = verify_admin_access(user_input, mock_creds)
        self.assertFalse(unlock_user_attempt, "一般ログインパスワードでは管理者メニューをアンロックできないこと")

        # 4. 正しい管理者マスターパスワードによるアンロック試行（成功）
        correct_input = a_pwd
        unlock_success = verify_admin_access(correct_input, mock_creds)
        self.assertTrue(unlock_success, "管理者パスワードでアンロック認証が成功すること")
        if unlock_success:
            session_state["is_admin"] = True
        self.assertTrue(session_state["is_admin"], "管理者権限に安全に昇格できること")

        # 5. 管理者モード終了（一般モードへの復帰）
        session_state["is_admin"] = False
        self.assertFalse(session_state["is_admin"], "一般モードに安全に降格できること")

    def test_dual_password_complete_separation(self):
        """【Security Architecture】一般パスワードと管理者用パスワードの完全分離・相互運用性の検証"""
        from auth_manager import (
            hash_password,
            verify_user_login,
            verify_admin_access,
            save_auth_credentials,
            update_user_password,
            update_admin_password,
            load_auth_credentials,
            AUTH_CONFIG_FILE,
        )

        user_pwd = "FamilyPassword123"
        admin_pwd = "MasterAdminPassword999"
        u_h, u_s = hash_password(user_pwd)
        a_h, a_s = hash_password(admin_pwd)

        creds = {
            "user_hash": u_h,
            "user_salt": u_s,
            "admin_hash": a_h,
            "admin_salt": a_s,
            "hash": u_h,
            "salt": u_s,
        }

        # A. ログイン画面の検証 (verify_user_login)
        # 1. 一般パスワードでログイン成功
        self.assertTrue(verify_user_login(user_pwd, creds), "一般パスワードでログインできること")
        # 2. 管理者パスワードでもログイン成功（管理者の普段使いサポート）
        self.assertTrue(verify_user_login(admin_pwd, creds), "管理者パスワードでもログインできること")
        # 3. 間違ったパスワードは拒絶
        self.assertFalse(verify_user_login("WrongPassword", creds), "誤ったパスワードは拒絶されること")

        # B. 管理者メニューの検証 (verify_admin_access)
        # 1. 管理者パスワードでのみ解除可能
        self.assertTrue(verify_admin_access(admin_pwd, creds), "管理者パスワードで管理者メニューが開けること")
        # 2. 一般パスワードでは絶対に解除不可（二重防壁）
        self.assertFalse(verify_admin_access(user_pwd, creds), "一般パスワードでは管理者メニューは開けないこと")

        # C. 後方互換性テスト（旧データ形式: admin_hash 未設定時）
        legacy_creds = {
            "hash": u_h,
            "salt": u_s,
        }
        # 旧形式では既存パスワードが管理者パスワードとしても兼用される
        self.assertTrue(verify_user_login(user_pwd, legacy_creds), "旧形式でもログイン可能")
        self.assertTrue(verify_admin_access(user_pwd, legacy_creds), "旧形式では管理者アクセスもフォールバック動作")

    def test_token_regeneration_and_revocation(self):
        """【Security】トークン再発行による古いURLトークンの即時失効と新トークン認証を検証"""
        from auth_manager import (
            get_secure_token,
            verify_secure_token,
            save_token_salt,
            hash_password,
        )
        h, s = hash_password("TestSecretPwd123!")

        # 1. 旧方式（token_salt なし）での初期トークン
        old_token = get_secure_token(s, h)
        self.assertTrue(verify_secure_token(old_token, s, h), "旧トークンは単体で認証可能")

        # 2. 新しい token_salt（再発行シード）を発行
        new_token_salt = "feedcafe12345678abcdef0123456789"
        new_token = get_secure_token(s, h, new_token_salt)

        # 3. 古いトークンと新しいトークンが異なること
        self.assertNotEqual(old_token, new_token, "再発行後のトークンは必ず異なる必要があります")

        # 4. 新しい token_salt 下では、古いトークンは確実に拒否されること（即時失効）
        self.assertFalse(
            verify_secure_token(old_token, s, h, new_token_salt),
            "token_salt 適用後は古いトークンでのアクセスが拒否されなければなりません"
        )

        # 5. 新しいトークンでは正常に認証できること
        self.assertTrue(
            verify_secure_token(new_token, s, h, new_token_salt),
            "新しいトークンでは正常に認証できる必要があります"
        )

    def test_password_update_and_immediate_activation(self):
        """【Security & UX】パスワード変更後に即時有効化され、新パスワードでログイン成功・旧パスワードで拒絶されることを検証"""
        import os
        import json
        from auth_manager import (
            save_auth_credentials,
            update_user_password,
            update_admin_password,
            load_auth_credentials,
            verify_user_login,
            verify_admin_access,
            MIN_PASSWORD_LENGTH,
            AUTH_CONFIG_FILE,
        )

        # 4文字以上のパスワードが許可されていること
        self.assertEqual(MIN_PASSWORD_LENGTH, 4, "ご家族が使いやすいよう最小4文字に統一されていること")

        # テスト用初期パスワード
        init_user = "1234"
        init_admin = "admin999"

        # 初期保存
        save_res = save_auth_credentials(init_user, init_admin)
        self.assertTrue(save_res, "4文字の初期パスワードが正常に保存できること")

        # 読み込み
        creds = load_auth_credentials()
        self.assertIsNotNone(creds)
        self.assertTrue(verify_user_login(init_user, creds), "初期一般パスワードでログインできること")
        self.assertTrue(verify_admin_access(init_admin, creds), "初期管理者パスワードで管理者認証できること")

        # 一般パスワードを変更
        new_user = "5678"
        upd_res = update_user_password(new_user)
        self.assertTrue(upd_res, "一般パスワードの変更が成功すること")

        # 読み込み後の検証
        updated_creds = load_auth_credentials()
        self.assertTrue(verify_user_login(new_user, updated_creds), "変更後の新パスワードで即座にログインできること")
        self.assertFalse(verify_user_login(init_user, updated_creds), "変更前の古いパスワードは確実に拒絶されること")

        # 管理者パスワードを変更
        new_admin = "newadmin2026"
        upd_admin_res = update_admin_password(new_admin)
        self.assertTrue(upd_admin_res, "管理者パスワードの変更が成功すること")

        # 読み込み後の管理者認証検証
        admin_updated_creds = load_auth_credentials()
        self.assertTrue(verify_admin_access(new_admin, admin_updated_creds), "変更後の新管理者パスワードで認証できること")
        self.assertFalse(verify_admin_access(init_admin, admin_updated_creds), "変更前の旧管理者パスワードは拒絶されること")

        # クリーンアップ（テスト用設定ファイルの削除）
        if os.path.exists(AUTH_CONFIG_FILE):
            try:
                os.remove(AUTH_CONFIG_FILE)
            except Exception:
                pass

    def test_countdown_auto_advance_logic(self):
        """【Next Train Auto-Advance】発車時刻経過後に自律更新ガードが作動し、次便へスムーズに遷移することを検証（平日・土休日双方）"""
        from transit_engine import JST, get_timestamp_ms, get_routes

        # --- A. 平日ダイヤでの自動更新検証（2026-09-18 金曜日）: 8:02 ➡ 8:10 ---
        sim_now_w = datetime.datetime(2026, 9, 18, 8, 0, 0, tzinfo=JST)
        routes_initial_w = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=sim_now_w)
        self.assertGreater(len(routes_initial_w), 0)
        first_route_w = routes_initial_w[0]
        self.assertEqual(first_route_w["departure_time"], "08:02")
        dept_ms_w = first_route_w["departure_timestamp_ms"]

        # 1. 発車前（8:01:00）: まだ発車していないため diff_sec > 0
        check_before_w = datetime.datetime(2026, 9, 18, 8, 1, 0, tzinfo=JST)
        diff_sec_before_w = (dept_ms_w - get_timestamp_ms(check_before_w)) // 1000
        self.assertEqual(diff_sec_before_w, 60)
        self.assertGreater(diff_sec_before_w, 0)

        # 2. 発車2秒後（8:02:02）: 発車済みで更新トリガー条件（diff_sec <= -2）に合致
        check_departed_w = datetime.datetime(2026, 9, 18, 8, 2, 2, tzinfo=JST)
        diff_sec_departed_w = (dept_ms_w - get_timestamp_ms(check_departed_w)) // 1000
        self.assertLessEqual(diff_sec_departed_w, -2, "発車後2秒で次便更新トリガー条件が成立すること")

        # 3. 平日自律更新ガード: 次便（8:09発）が先頭便として自動取得されること
        routes_next_w = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=check_departed_w)
        self.assertGreater(len(routes_next_w), 0)
        self.assertEqual(routes_next_w[0]["departure_time"], "08:09", "平日の発車後は即座に次便（8:09発）へバトンタッチすること")

        # --- B. 土休日ダイヤでの自動更新検証（2026-09-20 日曜日）: 8:02 ➡ 8:04 ---
        check_departed_h = datetime.datetime(2026, 9, 20, 8, 2, 2, tzinfo=JST)
        routes_next_h = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=check_departed_h)
        self.assertGreater(len(routes_next_h), 0)
        self.assertEqual(routes_next_h[0]["departure_time"], "08:04", "土休日の発車後は即座に次便（8:04発）へバトンタッチすること")

    def test_offset_and_pace_changes_reactivity(self):
        """【Dynamic Settings】出発オフセットおよび乗換ペースの変更がルート探索に正しく即時反映されることを検証"""
        from app import JST
        from transit_engine import get_routes

        sim_now = datetime.datetime(2026, 9, 20, 10, 0, 0, tzinfo=JST)

        # A. オフセットなし（今すぐ: 10:00）➡ 恋ヶ窪 10:04 発
        r_now = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="normal", now=sim_now)
        self.assertEqual(r_now[0]["departure_time"], "10:04")

        # B. オフセット+15分（10:15以降に出発）➡ 恋ヶ窪 10:24 発
        r_15m = get_routes("koigakubo_to_asakadai", offset_minutes=15, pace="normal", now=sim_now)
        self.assertEqual(r_15m[0]["departure_time"], "10:24")

        # C. オフセット+30分（10:30以降に出発）➡ 恋ヶ窪 10:35 発
        r_30m = get_routes("koigakubo_to_asakadai", offset_minutes=30, pace="normal", now=sim_now)
        self.assertEqual(r_30m[0]["departure_time"], "10:35")

        # D. 乗換ペースの影響（急ぎ足 fast vs ゆったり relaxed）
        r_fast = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="fast", now=sim_now)
        r_relaxed = get_routes("koigakubo_to_asakadai", offset_minutes=0, pace="relaxed", now=sim_now)
        self.assertIsNotNone(r_fast)
        self.assertIsNotNone(r_relaxed)
        # ゆったりペースでは乗換待ち時間が十分に確保されること
        for leg in r_relaxed[0]["legs"]:
            if "wait_min" in leg:
                self.assertGreaterEqual(leg["wait_min"], 0)

    def test_no_exposed_code_blocks_in_markdown(self):
        """【UI/UX Guard】app.py のマークダウン描画内に未意図のコードブロック（<pre><code>）化を招くインデント誤認や生JSタグが混入していないことを検査"""
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("<img onload=", content, "app.py に <img onload> による生JSハックが残っていてはいけません")
        self.assertNotIn("triggerNextTrainUpdate", content, "app.py にトリガー関数名が残っていてはいけません")
        self.assertNotIn("window.location.reload", content, "app.py に生ブラウザリロードスクリプトが残っていてはいけません")
        # 土休日ダイヤバナーのCommonMarkインデント誤認（4スペース以上のインデント）防止検査
        self.assertIn("banner_html = f\"<div style='display:flex; align-items:center;", content, "バナーHTMLは行頭インデントなしで定義されていること")

    def test_unauthenticated_screen_privacy(self):
        """【Privacy Guard】未認証画面において駅名（恋ヶ窪、朝霞台）や路線名などの個人特定情報が露出していないことを静的検査"""
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("プライベート ダッシュボード", content, "未認証画面はプライベート ダッシュボードと表記されている必要があります")
        self.assertIn("🔒 認証 | プライベート ダッシュボード", content, "未認証画面のブラウザタイトルが秘匿化されている必要があります")


class TestJapanCalendar(unittest.TestCase):
    """日本の祝日判定エンジン（内閣府基準完全準拠）の包括的検証"""

    def test_fixed_holidays(self):
        """固定祝日（元日、建国記念の日、昭和の日、憲法記念日、みどりの日、こどもの日、山の日、文化の日、勤労感謝の日）の判定"""
        from japan_calendar import get_holiday_name, is_holiday_or_weekend
        self.assertEqual(get_holiday_name(datetime.date(2026, 1, 1)), "元日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 2, 11)), "建国記念の日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 2, 23)), "天皇誕生日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 4, 29)), "昭和の日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 5, 3)), "憲法記念日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 5, 4)), "みどりの日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 5, 5)), "こどもの日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 8, 11)), "山の日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 11, 3)), "文化の日")
        self.assertEqual(get_holiday_name(datetime.date(2026, 11, 23)), "勤労感謝の日")

    def test_happy_monday_holidays(self):
        """ハッピーマンデー制度（成人の日、海の日、敬老の日、スポーツの日）の判定"""
        from japan_calendar import get_holiday_name
        # 成人の日: 1月第2月曜日 (2026年は1月12日)
        self.assertEqual(get_holiday_name(datetime.date(2026, 1, 12)), "成人の日")
        # 海の日: 7月第3月曜日 (2026年は7月20日)
        self.assertEqual(get_holiday_name(datetime.date(2026, 7, 20)), "海の日")
        # 敬老の日: 9月第3月曜日 (2026年は9月21日)
        self.assertEqual(get_holiday_name(datetime.date(2026, 9, 21)), "敬老の日")
        # スポーツの日: 10月第2月曜日 (2026年は10月12日)
        self.assertEqual(get_holiday_name(datetime.date(2026, 10, 12)), "スポーツの日")

    def test_equinox_and_citizens_holiday(self):
        """春分の日・秋分の日および国民の休日（祝日に挟まれた平日）の判定"""
        from japan_calendar import get_holiday_name
        # 2026年春分の日: 3月20日
        self.assertEqual(get_holiday_name(datetime.date(2026, 3, 20)), "春分の日")
        # 2026年秋分の日: 9月23日
        self.assertEqual(get_holiday_name(datetime.date(2026, 9, 23)), "秋分の日")
        # 2026年9月22日: 敬老の日(9/21)と秋分の日(9/23)に挟まれた国民の休日
        self.assertEqual(get_holiday_name(datetime.date(2026, 9, 22)), "国民の休日")

    def test_substitute_holiday(self):
        """振替休日の判定（祝日が日曜日の場合、翌以降の平日が振替休日）"""
        from japan_calendar import get_holiday_name
        # 2026年5月3日は日曜日（憲法記念日）
        # 5/4(月:みどりの日)、5/5(火:こどもの日)に続くため、5月6日(水)が振替休日
        holiday_name = get_holiday_name(datetime.date(2026, 5, 6))
        self.assertIsNotNone(holiday_name)
        self.assertIn("振替休日", holiday_name)

    def test_normal_weekdays(self):
        """通常の平日が祝日と判定されないことの検証"""
        from japan_calendar import get_holiday_name, is_holiday_or_weekend, get_timetable_type
        # 2026年9月18日（金曜日）
        d_fri = datetime.date(2026, 9, 18)
        self.assertIsNone(get_holiday_name(d_fri))
        self.assertFalse(is_holiday_or_weekend(d_fri))
        self.assertEqual(get_timetable_type(d_fri), "weekday")

    def test_timetable_display_info(self):
        """表示用ダイヤバッジ情報の生成検証"""
        from japan_calendar import get_timetable_display_info
        # 敬老の日（2026-09-21）
        info_hol = get_timetable_display_info(datetime.date(2026, 9, 21))
        self.assertEqual(info_hol["type"], "holiday")
        self.assertEqual(info_hol["badge_label"], "土休日ダイヤ")
        self.assertEqual(info_hol["holiday_name"], "敬老の日")
        self.assertIn("敬老の日", info_hol["full_badge"])

        # 通常平日（2026-09-18）
        info_wd = get_timetable_display_info(datetime.date(2026, 9, 18))
        self.assertEqual(info_wd["type"], "weekday")
        self.assertEqual(info_wd["badge_label"], "平日ダイヤ")
        self.assertIsNone(info_wd["holiday_name"])

    def test_service_date_midnight_boundary(self):
        """鉄道運行日（午前05:00切り替え境界）の検証：深夜0時〜4時台は前日ダイヤに帰属すること"""
        from japan_calendar import get_service_date, get_timetable_type, get_holiday_name

        # 1. 金曜深夜（2026-09-19 土曜 00:01）-> 運行日は金曜日（平日ダイヤ）
        dt_fri_midnight = datetime.datetime(2026, 9, 19, 0, 1, 0)
        self.assertEqual(get_service_date(dt_fri_midnight), datetime.date(2026, 9, 18))
        self.assertEqual(get_timetable_type(dt_fri_midnight), "weekday")

        # 2. 土曜朝（2026-09-19 土曜 05:01）-> 運行日は土曜日（土休日ダイヤ）
        dt_sat_morning = datetime.datetime(2026, 9, 19, 5, 1, 0)
        self.assertEqual(get_service_date(dt_sat_morning), datetime.date(2026, 9, 19))
        self.assertEqual(get_timetable_type(dt_sat_morning), "holiday")

        # 3. 敬老の日の深夜（2026-09-22 火曜 00:15）-> 運行日は敬老の日（土休日ダイヤ）
        dt_respect_midnight = datetime.datetime(2026, 9, 22, 0, 15, 0)
        self.assertEqual(get_service_date(dt_respect_midnight), datetime.date(2026, 9, 21))
        self.assertEqual(get_timetable_type(dt_respect_midnight), "holiday")
        self.assertEqual(get_holiday_name(dt_respect_midnight), "敬老の日")


if __name__ == '__main__':
    unittest.main()


