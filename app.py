"""
恋朝トレインタイマー (Koiasa Train Timer)
恋ヶ窪 ⇔ 北朝霞 リアルタイム電車ナビゲーション・ダッシュボード
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
    verify_user_login,
    verify_admin_access,
    update_user_password,
    update_admin_password,
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

from japan_calendar import (
    get_holiday_name,
    is_holiday_or_weekend,
    get_timetable_type,
    get_timetable_display_info,
)
from timetable_data import (
    TIMETABLE_VERSION,
    LAST_VERIFIED_DATE,
    KOIGAKUBO_DEPARTURES,
    KOKUBUNJI_CHUO_DOWN,
    NISHI_KOKUBUNJI_MUSASHINO_UP,
    KITA_ASAKADAI_MUSASHINO_DOWN,
    NISHI_KOKUBUNJI_CHUO_UP,
    KOKUBUNJI_SEIBU_DOWN,
    KOIGAKUBO_DEPARTURES_WEEKDAY,
    KOIGAKUBO_DEPARTURES_HOLIDAY,
    LINE_INFO,
    TIMETABLES,
    get_timetable_set,
)
from transit_engine import (
    JST,
    get_timestamp_ms,
    escape_text,
    is_safe_url,
    get_default_direction,
    find_next_departure,
    find_next_departures_list,
    get_transfer_buffer,
    calculate_koigakubo_to_asakadai,
    calculate_asakadai_to_koigakubo,
    get_routes,
    get_last_train_info,
)

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
# 認証状態に応じたブラウザタイトル（未認証時は駅名を完全隠蔽し個人情報を徹底保護）
is_authed = bool(st.session_state.get("authenticated", False))
app_page_title = "恋朝トレインタイマー | 恋ヶ窪 ⇔ 北朝霞" if is_authed else "🔒 認証 | プライベート ダッシュボード"
app_page_icon = "🚆" if is_authed else "🔒"

st.set_page_config(
    page_title=app_page_title,
    page_icon=app_page_icon,
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
       European Sunrise & Sunflower Design System (V4.0)
       Warm Modernism / European Human-Centered Spec (Copenhagen & Provence Sunrise)
       ========================================================================== */
    :root {
        --bg-base: #FFFDF9;
        --surface-card: #FFFFFF;
        --surface-hero: radial-gradient(circle at 85% 15%, rgba(254, 240, 138, 0.32) 0%, transparent 55%), linear-gradient(135deg, #C2410C 0%, #EA580C 28%, #F97316 65%, #FBBF24 100%);
        --surface-glass: rgba(67, 20, 7, 0.20);
        --border-subtle: #F3E8D6;
        --border-card: #EADBC8;
        --border-glass: rgba(254, 240, 138, 0.45);
        --text-primary: #1C1917;
        --text-secondary: #57534E;
        --text-muted: #78716C;
        --text-light: #A8A29E;
        --accent-sun-orange: #EA580C;
        --accent-sun-amber: #F59E0B;
        --accent-sun-gold: #FBBF24;
        --accent-emerald: #10B981;
        --accent-rose: #EF4444;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --shadow-sm: 0 1px 3px rgba(67, 20, 7, 0.04);
        --shadow-md: 0 4px 14px -2px rgba(67, 20, 7, 0.06), 0 2px 4px rgba(67, 20, 7, 0.02);
        --shadow-hero: 0 14px 34px -4px rgba(234, 88, 12, 0.38), 0 6px 14px rgba(194, 65, 12, 0.20);
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
        border-bottom: 1px solid #F3E8D6;
    }
    .brand-block {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .brand-logo-badge {
        background: linear-gradient(135deg, #EA580C 0%, #F97316 45%, #FBBF24 100%);
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 17px;
        box-shadow: 0 2px 8px rgba(234, 88, 12, 0.32);
    }
    .brand-text-group {
        display: flex;
        flex-direction: column;
    }
    .brand-name {
        font-size: 0.98rem;
        font-weight: 800;
        color: #1C1917;
        letter-spacing: -0.02em;
        line-height: 1.15;
    }
    .brand-sub {
        font-size: 0.6rem;
        font-weight: 700;
        color: #9A3412;
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
        border: 1px solid #F3E8D6;
        padding: 3px 8px;
        border-radius: 9999px;
        box-shadow: var(--shadow-sm);
    }
    .pulse-dot {
        width: 7px;
        height: 7px;
        background-color: #F59E0B;
        border-radius: 9999px;
        box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.3);
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
        color: #44403C;
    }
    .version-tag {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 700;
        color: #9A3412;
        background: #FEF3C7;
        border: 1px solid #FCD34D;
        padding: 2px 7px;
        border-radius: 6px;
    }

    /* 2. 行き先切り替え（Apple HIG 48px タップターゲット & 朝日サンバーストUI） */
    .stButton > button {
        border-radius: 14px !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        min-height: 48px !important;
        padding: 8px 10px !important;
        border: 1px solid #EADBC8 !important;
        background: #FFFFFF !important;
        color: #44403C !important;
        box-shadow: 0 1px 3px rgba(67, 20, 7, 0.04) !important;
        transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
        white-space: pre-line !important;
        line-height: 1.25 !important;
    }
    .stButton > button:hover {
        background: #FFFDF9 !important;
        color: #1C1917 !important;
        border-color: #FBBF24 !important;
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(245, 158, 11, 0.12) !important;
    }
    .stButton > button:active {
        transform: translateY(1px);
        box-shadow: 0 1px 2px rgba(67, 20, 7, 0.04) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #EA580C 0%, #F97316 48%, #FBBF24 100%) !important;
        color: #FFFFFF !important;
        border-color: #C2410C !important;
        box-shadow: 0 4px 14px rgba(234, 88, 12, 0.34) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #C2410C 0%, #EA580C 48%, #F59E0B 100%) !important;
        border-color: #9A3412 !important;
        box-shadow: 0 6px 18px rgba(234, 88, 12, 0.42) !important;
    }

    /* 3. ヒーロー・カウントダウンカード（Sunrise Dawn & Sunflower Glow） */
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
        height: 1.5px;
        background: linear-gradient(90deg, rgba(251,191,36,0) 0%, rgba(251,191,36,0.6) 50%, rgba(251,191,36,0) 100%);
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
        color: #FED7AA;
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
        background: rgba(254, 240, 138, 0.18);
        color: #FEF08A;
        border: 1px solid rgba(254, 240, 138, 0.35);
    }
    .badge-urgent {
        background: var(--accent-rose);
        color: #FFFFFF;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
        animation: urgent-pulse 1.2s infinite;
    }
    .badge-departed {
        background: rgba(120, 113, 108, 0.85);
        color: #FEF08A;
        border: 1px solid rgba(254, 240, 138, 0.4);
        animation: departed-pulse 1.4s infinite ease-in-out;
    }
    @keyframes departed-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.65; transform: scale(0.98); }
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
        text-shadow: 0 2px 14px rgba(67, 20, 7, 0.55);
    }
    .hero-digits .unit {
        font-size: 1.1rem;
        font-weight: 600;
        color: #FED7AA;
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
        border: 1px solid rgba(254, 240, 138, 0.35);
        margin-top: 4px;
        backdrop-filter: blur(8px);
    }
    .hero-st-block {
        display: flex;
        flex-direction: column;
    }
    .hero-st-name {
        font-size: 0.78rem;
        color: #FED7AA;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .hero-st-time {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 1.35rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.15;
    }
    .hero-st-time.arrival {
        color: #FEF08A;
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
        color: #FEF08A;
        background: rgba(251, 191, 36, 0.22);
        border: 1px solid rgba(251, 191, 36, 0.45);
        padding: 2px 8px;
        border-radius: 9999px;
    }

    /* 終電案内行（高コントラスト・極上視認性・ダークすりガラスバッジ） */
    .hero-last-train-row {
        font-size: 0.74rem;
        background: rgba(35, 10, 2, 0.42);
        border: 1px solid rgba(254, 240, 138, 0.50);
        border-radius: 10px;
        padding: 6px 12px;
        margin-top: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        backdrop-filter: blur(8px);
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.28), 0 1px 3px rgba(0, 0, 0, 0.12);
    }
    .hero-last-train-label {
        font-weight: 700;
        color: #FEF08A;
        display: flex;
        align-items: center;
        gap: 5px;
        letter-spacing: 0.02em;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
    }
    .hero-last-train-val {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 800;
        color: #FFFFFF;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
        letter-spacing: 0.01em;
    }

    /* 4. 統合メトロ・タイムラインボード (Clean Sunflower White Card) */
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
        border-bottom: 1px solid #FAF6EE;
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
        color: #44403C !important;
        padding: 12px 16px !important;
        transition: background 0.15s;
    }
    div[data-testid="stExpander"] details summary:hover {
        background: #FFFDF9 !important;
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
        <div style="background:linear-gradient(135deg, #EA580C 0%, #F97316 50%, #FBBF24 100%); color:white; width:64px; height:64px; border-radius:20px; display:inline-flex; align-items:center; justify-content:center; margin-bottom:12px; box-shadow:0 6px 18px rgba(234,88,12,0.3);">
            <span class="material-symbols-outlined" style="font-size:32px; color:#FEF08A;">shield_person</span>
        </div>
        <h2 style="font-size:1.3rem; font-weight:900; color:#9A3412; margin:0 0 6px 0;">初期セキュリティ設定</h2>
        <p style="font-size:0.8rem; color:#78716C; margin:0 0 16px 0;">本アプリはプライベート利用専用です。<br>ご利用を開始する前に、安全なパスワード（4文字以上）を設定してください。</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("setup_password_form", clear_on_submit=False):
        st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#9A3412; margin-bottom:2px;'>① 一般ログインパスワード（ご家族用）</div>", unsafe_allow_html=True)
        setup_user_pass = st.text_input("ご家族向けログインパスワード（4文字以上）", type="password", placeholder="例: 家族で共有するパスワード")
        setup_user_confirm = st.text_input("ご家族向けログインパスワード（再入力）", type="password", placeholder="同じパスワードを再入力")

        st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#9A3412; margin:12px 0 2px 0;'>② 管理者用マスターパスワード（管理者様専用）</div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:0.72rem; color:#78716C; margin:0 0 4px 0;'>※設定変更やURL再発行を行うための専用パスワードです。未入力の場合は上記一般パスワードと同じになります。</p>", unsafe_allow_html=True)
        setup_admin_pass = st.text_input("管理者専用パスワード（4文字以上・任意）", type="password", placeholder="管理者専用パスワード（省略可）")

        setup_submit = st.form_submit_button("パスワードを登録して起動 🔒", use_container_width=True, type="primary")

        if setup_submit:
            if len(setup_user_pass) < MIN_PASSWORD_LENGTH:
                st.error(f"❌ 一般ログインパスワードは{MIN_PASSWORD_LENGTH}文字以上で設定してください。")
            elif setup_user_pass != setup_user_confirm:
                st.error("❌ 一般ログインパスワードの再確認が一致しません。")
            elif setup_admin_pass and len(setup_admin_pass) < MIN_PASSWORD_LENGTH:
                st.error(f"❌ 管理者用パスワードを設定する場合は{MIN_PASSWORD_LENGTH}文字以上で設定してください。")
            else:
                admin_p = setup_admin_pass if setup_admin_pass else None
                if save_auth_credentials(setup_user_pass, admin_p):
                    st.session_state["authenticated"] = True
                    st.session_state["is_admin"] = bool(admin_p)
                    sec_mgr.record_success()
                    st.success("✅ パスワードを設定しました。アプリを起動します...")
                    st.rerun()
                else:
                    st.error("❌ パスワードの保存に失敗しました。ファイル書き込み権限をご確認ください。")

    st.markdown("""
    <div style="text-align:center; margin-top:24px; font-size:0.75rem; color:#A8A29E;">
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
        <div style="background:linear-gradient(135deg, #EA580C 0%, #F97316 50%, #FBBF24 100%); color:white; width:64px; height:64px; border-radius:20px; display:inline-flex; align-items:center; justify-content:center; margin-bottom:12px; box-shadow:0 6px 18px rgba(234,88,12,0.3);">
            <span class="material-symbols-outlined" style="font-size:32px; color:#FEF08A;">lock</span>
        </div>
        <h2 style="font-size:1.3rem; font-weight:900; color:#9A3412; margin:0 0 4px 0;">プライベート ダッシュボード</h2>
        <div style="display:inline-block; background:#FEF3C7; border:1px solid #FCD34D; padding:2px 10px; border-radius:12px; font-size:0.75rem; font-weight:800; color:#9A3412; margin-bottom:10px;">V4.0</div>
        <p style="font-size:0.8rem; color:#78716C; margin:0 0 16px 0;">このアプリは非公開設定されています。<br>ご利用にはパスワードが必要です。</p>
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
            if verify_user_login(input_pass, credentials):
                st.session_state["authenticated"] = True
                # 管理者パスワードで直接ログインした場合は管理者権限も有効化
                if verify_admin_access(input_pass, credentials):
                    st.session_state["is_admin"] = True
                else:
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
    <div style="text-align:center; margin-top:24px; font-size:0.75rem; color:#A8A29E;">
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
if "timetable_mode" not in st.session_state:
    st.session_state["timetable_mode"] = "auto"

# ----------------------------------------------------
# 1. 【最上部】行き先設定（堅牢なステートレス・ボタングループ）
# ----------------------------------------------------
is_k2a = (st.session_state["direction"] == "koigakubo_to_asakadai")

# 本日のダイヤ種別（平日/土休日/祝日）の自動判定 & プレビュー適応
auto_tt_info = get_timetable_display_info(now_jst)
tt_mode = st.session_state.get("timetable_mode", "auto")

if tt_mode == "weekday":
    active_timetable_type = "weekday"
    is_manual = True
    active_label = "平日ダイヤ（手動プレビュー中）"
    active_holiday_name = None
    active_bg = "rgba(16, 185, 129, 0.08)"
    active_border = "#A7F3D0"
    active_text_color = "#065F46"
    active_icon = "💼"
    active_notice = "※平日の運行ダイヤを手動表示中"
elif tt_mode == "holiday":
    active_timetable_type = "holiday"
    is_manual = True
    active_label = "土休日ダイヤ（手動プレビュー中）"
    active_holiday_name = None
    active_bg = "rgba(234, 88, 12, 0.08)"
    active_border = "#FDBA74"
    active_text_color = "#C2410C"
    active_icon = "📅"
    active_notice = "※土休日の運行ダイヤを手動表示中"
else:
    # 365日24時間 完全自動判定モード（デフォルト）
    active_timetable_type = auto_tt_info["type"]
    is_manual = False
    is_holiday = (auto_tt_info["type"] == "holiday")
    active_label = auto_tt_info["badge_label"]
    active_holiday_name = auto_tt_info.get("holiday_name")
    active_bg = "rgba(234, 88, 12, 0.08)" if is_holiday else "rgba(16, 185, 129, 0.08)"
    active_border = "#FDBA74" if is_holiday else "#A7F3D0"
    active_text_color = "#C2410C" if is_holiday else "#065F46"
    active_icon = "📅" if is_holiday else "💼"
    active_notice = "⚠️ 土休日ダイヤ運行中（終電時刻にご注意ください）" if is_holiday else ""

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
        <span class="version-tag">V4.3</span>
    </div>
</div>
""", unsafe_allow_html=True)

col_d1, col_d2, col_rv = st.columns([5, 5, 2])
with col_d1:
    btn_k2a_text = "📍 恋ヶ窪 ➡ 北朝霞" if is_k2a else "恋ヶ窪 ➡ 北朝霞"
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
    btn_a2k_text = "📍 北朝霞 ➡ 恋ヶ窪" if not is_k2a else "北朝霞 ➡ 恋ヶ窪"
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

# ダイヤ種別ステータスバナー（祝日・土日・平日の完全自動判定表示）
# Markdownパーサーによる空行＋4スペース誤認（コードブロック化）を完全に排除するため、インデントなしの純粋HTMLを組み立てる
banner_elements = [
    f"<span style='font-size:0.82rem; font-weight:800; color:{active_text_color}; display:flex; align-items:center; gap:4px;'><span>{active_icon}</span><span>{active_label}</span></span>"
]
if active_holiday_name:
    banner_elements.append(f"<span style='font-size:0.75rem; font-weight:700; background:#FEF3C7; color:#92400E; padding:1px 6px; border-radius:4px; margin-left:4px;'>祝日: {escape_text(active_holiday_name)}</span>")
if active_notice:
    banner_elements.append(f"<span style='font-size:0.72rem; color:{active_text_color}; font-weight:600; margin-left:auto;'>{active_notice}</span>")

banner_html = f"<div style='display:flex; align-items:center; flex-wrap:wrap; gap:6px; background:{active_bg}; border:1px solid {active_border}; border-radius:10px; padding:6px 12px; margin:8px 0 12px 0;'>{''.join(banner_elements)}</div>"
st.markdown(banner_html, unsafe_allow_html=True)

if is_manual:
    col_rst1, col_rst2 = st.columns([7, 3])
    with col_rst2:
        if st.button("↩️ 自動判定に戻す", key="btn_reset_tt_mode", use_container_width=True):
            st.session_state["timetable_mode"] = "auto"
            st.session_state["selected_index"] = 0
            st.rerun()

# ダイヤ改正検知ステータス & 終電情報（確定した direction & ダイヤ種別に基づく）
revision_info = get_revision_status()
last_train = get_last_train_info(st.session_state["direction"], now=now_jst, timetable_type=active_timetable_type)

# ----------------------------------------------------
# 2. リアルタイム経路計算 & クライアント自律型秒針エンジン
# ----------------------------------------------------
routes = get_routes(
    direction=st.session_state["direction"],
    offset_minutes=st.session_state["offset_minutes"],
    pace=st.session_state["pace"],
    now=now_jst,
    timetable_type=active_timetable_type
)

if not routes:
    st.warning("本日の運行は終了いたしました。")
    st.stop()

# 選択便の安全検証（インデックス範囲チェック）
if "selected_index" not in st.session_state:
    st.session_state["selected_index"] = 0
selected_idx = min(st.session_state["selected_index"], len(routes) - 1)
current_route = routes[selected_idx]

# 【自律更新ガード】もし選択中の便がすでに発車時刻を過ぎている（1秒以上過去）場合、
# 過去便が残り続けるのを防ぐため、最速便（インデックス0）に安全リセットして再取得
now_ms_check = get_timestamp_ms(datetime.datetime.now(JST))
if current_route["departure_timestamp_ms"] < now_ms_check:
    st.session_state["selected_index"] = 0
    routes = get_routes(
        direction=st.session_state["direction"],
        offset_minutes=st.session_state["offset_minutes"],
        pace=st.session_state["pace"],
        now=datetime.datetime.now(JST)
    )
    if not routes:
        st.warning("本日の運行は終了いたしました。")
        st.stop()
    selected_idx = 0
    current_route = routes[0]

dept_station = "恋ヶ窪" if st.session_state["direction"] == "koigakubo_to_asakadai" else "北朝霞"
arrv_station = "北朝霞" if st.session_state["direction"] == "koigakubo_to_asakadai" else "恋ヶ窪"

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
    diff_sec = (dept_timestamp_ms - now_ms) // 1000
    left_sec = max(0, diff_sec)
    min_left = left_sec // 60
    sec_left = left_sec % 60
    min_str = f"{min_left:02d}"
    sec_str = f"{sec_left:02d}"

    if diff_sec <= 0:
        badge_class = "badge-departed"
        badge_text = "発車しました（次の便へ更新中...）"
        min_str = "00"
        sec_str = "00"
        # 発車後約2秒経過したらアプリ全体を安全に再計算して次便へ移行
        if diff_sec <= -2:
            st.session_state["selected_index"] = 0
            st.cache_data.clear()
            try:
                st.rerun(scope="app")
            except TypeError:
                st.rerun()
    elif left_sec <= 120:
        badge_class = "badge-urgent"
        badge_text = "まもなく発車"
    else:
        badge_class = "badge-normal"
        badge_text = "NEXT DEPARTURE"

    clock_str = f"{now_dt.hour:02d}:{now_dt.minute:02d}:{now_dt.second:02d}"

    html_snippet = f"""<div class="hero-timer-card">
    <div class="hero-timer-header">
        <span class="hero-micro-label">⏱️ 次の発車まで</span>
        <div><span id="hero-status-badge" class="badge {badge_class}">{badge_text}</span></div>
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
            <div style="display:flex; align-items:center; justify-content:center; margin-top:2px;">
                <svg width="24" height="13" viewBox="0 0 24 13" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter:drop-shadow(0 1px 3px rgba(0,0,0,0.5));">
                    <path d="M1 6.5H21M21 6.5L15.5 1.5M21 6.5L15.5 11.5" stroke="#FEF08A" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>
        </div>
        <div class="hero-st-block" style="text-align:right;">
            <div class="hero-st-name">{arrv_station} 着</div>
            <div class="hero-st-time arrival">{arrv_time}</div>
        </div>
    </div>
    <div class="hero-last-train-row">
        <span class="hero-last-train-label">🌙 今夜の最終便案内</span>
        <span class="hero-last-train-val">{dept_station} <span style="color:#FEF08A; font-weight:900;">{last_train_dept}</span> 発（所要 <span style="color:#FEF08A; font-weight:800;">{last_train_duration}分</span>）</span>
    </div>
</div>"""
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
            <span class="material-symbols-outlined" style="font-size:16px; color:#EA580C;">route</span>
            <span style="color:#1C1917; font-weight:800;">乗換ルート詳細</span>
        </span>
        <span style="font-size:0.65rem; color:#78716C; font-weight:700; background:#FAF6EE; padding:2px 8px; border-radius:12px; border:1px solid #F3E8D6;">3区間 / 乗換2回</span>
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
        <div style="width:12px; height:12px; border-radius:9999px; border:3px solid {color}; background:#FFFFFF; flex-shrink:0; box-shadow:0 0 0 2px rgba(67,20,7,0.04);"></div>
        <div style="font-size:0.92rem; font-weight:800; color:#1C1917; letter-spacing:-0.01em;">{from_st}</div>
        <div style="font-size:0.68rem; color:#57534E; background:#FAF6EE; border:1px solid #F3E8D6; padding:1px 6px; border-radius:6px; font-weight:600;">{platform}</div>
    </div>
    <div style="font-family:'JetBrains Mono'; font-variant-numeric:tabular-nums; font-size:0.95rem; font-weight:800; color:#1C1917;">
        {f_time}
    </div>
</div>
"""

    # レール（移動区間）
    metro_html += f"""
<div style="display:flex; align-items:center; justify-content:space-between; margin-left:5px; padding: 4px 0 4px 15px; border-left: 2.5px solid {color};">
    <div style="font-size:0.76rem; color:#44403C; font-weight:600; display:flex; align-items:center; gap:5px;">
        <span style="color:{color}; font-size:0.7rem;">●</span>
        <span>{line_name}</span>
        <span style="color:#A8A29E; font-weight:500; font-size:0.72rem;">({dest})</span>
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
        <div style="font-size:0.92rem; font-weight:800; color:#1C1917; letter-spacing:-0.01em;">{to_st}</div>
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
<div style="display:flex; align-items:center; justify-content:space-between; margin-left:5px; padding: 4px 0 4px 15px; border-left: 2px dashed #EADBC8; font-size:0.72rem;">
    <span style="color:#78716C; font-weight:600; display:flex; align-items:center; gap:3px;">
        <span class="material-symbols-outlined" style="font-size:14px; color:#A8A29E;">transfer_within_a_station</span>
        <span>乗換待ち時間</span>
    </span>
    <span style="color:#C2410C; font-weight:700; background:#FFF7ED; padding:1.5px 7px; border-radius:6px; border:1px solid #FED7AA;">
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
    st.markdown(f"""<div style="font-size:0.75rem; font-weight:800; color:#44403C; letter-spacing:0.04em; margin: 14px 2px 8px 2px; display:flex; justify-content:space-between; align-items:center;">
    <span style="display:flex; align-items:center; gap:5px;">
        <span class="material-symbols-outlined" style="font-size:16px; color:#EA580C;">schedule</span>
        <span>その後の運行候補を比較</span>
    </span>
    <span style="font-size:0.68rem; color:#78716C; font-weight:700; background:#FAF6EE; border:1px solid #F3E8D6; padding:2px 8px; border-radius:10px;">全{len(routes)}候補</span>
</div>""", unsafe_allow_html=True)
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
with st.expander("⚙️ 出発タイミング ＆ 乗換・ダイヤ設定", expanded=False):
    c_off, c_pace = st.columns(2)
    with c_off:
        selected_offset = st.select_slider(
            "何分後に出発？",
            options=[0, 5, 10, 15, 30],
            format_func=lambda x: "今すぐ" if x == 0 else f"+{x}分後",
            value=st.session_state["offset_minutes"],
            key="slider_offset_val",
        )
        if selected_offset != st.session_state["offset_minutes"]:
            st.session_state["offset_minutes"] = selected_offset
            st.session_state["selected_index"] = 0
            st.rerun()

    with c_pace:
        pace_map = {"fast": "急ぎ足（最短接続）", "normal": "標準（おすすめ）", "relaxed": "ゆったり（余裕重視）"}
        selected_pace = st.selectbox(
            "乗換ゆとり度",
            options=["normal", "fast", "relaxed"],
            format_func=lambda x: pace_map.get(x, x),
            index=0 if st.session_state["pace"] == "normal" else 1 if st.session_state["pace"] == "fast" else 2,
            key="select_pace_val",
        )
        if selected_pace != st.session_state["pace"]:
            st.session_state["pace"] = selected_pace
            st.session_state["selected_index"] = 0
            st.rerun()

    # 運行ダイヤ自動判定 ＆ 任意プレビュー切り替え
    h_name = auto_tt_info.get("holiday_name")
    h_extra = f" - {h_name}" if h_name else ""
    auto_desc = f"🤖 完全自動判定（現在: {auto_tt_info['badge_label']}{h_extra}）"
    tt_labels = {
        "auto": auto_desc,
        "weekday": "💼 平日ダイヤをプレビュー確認",
        "holiday": "📅 土休日ダイヤをプレビュー確認",
    }
    cur_tt_idx = 0 if tt_mode == "auto" else 1 if tt_mode == "weekday" else 2
    selected_tt_mode = st.selectbox(
        "運行ダイヤの適用モード",
        options=["auto", "weekday", "holiday"],
        format_func=lambda x: tt_labels.get(x, x),
        index=cur_tt_idx,
        key="select_timetable_mode_val",
        help="【通常は『完全自動判定』のままでOK】365日24時間、祝日・土日・平日を全自動判定します。休日に平日のダイヤを事前確認したい場合などに切り替えてください。"
    )
    if selected_tt_mode != st.session_state["timetable_mode"]:
        st.session_state["timetable_mode"] = selected_tt_mode
        st.session_state["selected_index"] = 0
        st.rerun()


# 終電詳細カード（折りたたみ）
with st.expander(f"🌙 終電のご案内（最終連絡便: {last_train['departure_time']}発）", expanded=False):
    if last_train["is_expired"]:
        st.markdown(f"<div style='font-size:0.8rem; color:#64748B;'>本日の運行は終了いたしました（始発 {last_train['first_train_time']}）</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style="background:#FFFDF9; border:1px solid #EADBC8; border-radius:10px; padding:10px 14px; font-size:0.82rem; color:#1C1917; line-height:1.6; box-shadow:0 1px 3px rgba(67,20,7,0.04);">
    <strong style="color:#9A3412; font-size:0.88rem;">{last_train['departure_station']} {last_train['departure_time']}発 → {last_train['destination_station']} {last_train['arrival_time']}着</strong>（所要 <strong style="color:#C2410C;">{last_train['total_minutes']}分</strong>）<br>
    <span style="font-size:0.75rem; color:#44403C; font-weight:600;">ルート: {escape_text(last_train['route_summary'])}</span>
</div>""", unsafe_allow_html=True)

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
    with st.expander("🛠️ 管理者メニュー（管理者認証済み 🔓）", expanded=False):
        col_adm_head1, col_adm_head2 = st.columns([3, 2])
        with col_adm_head1:
            st.markdown("<div style='font-size:0.75rem; color:#059669; font-weight:700; padding:6px 0;'>🔓 管理者権限でロック解除中</div>", unsafe_allow_html=True)
        with col_adm_head2:
            if st.button("🔒 管理者モード終了", key="btn_exit_admin_top", use_container_width=True, help="一般画面に戻します（管理メニューを隠します）"):
                st.session_state["is_admin"] = False
                st.rerun()

        # パスワード変更完了時の即時案内メッセージ
        if st.session_state.pop("user_pwd_updated_notice", False):
            st.success("🎉 一般ログインパスワードを変更しました！今すぐ新しいパスワードでアクセスできます。")
            st.info("💡 **クラウド永続化（再起動対策）**: サーバー再起動後も新パスワードを恒久保持したい場合は、ページ下部の「☁️ クラウド恒久保存」に表示されている最新コードを Streamlit Cloud の管理画面（Secrets）に貼り付けてください。")

        if st.session_state.pop("admin_pwd_updated_notice", False):
            st.success("🎉 管理者用マスターパスワードを変更しました！次回から新しいパスワードをご使用ください。")
            st.info("💡 **クラウド永続化（再起動対策）**: サーバー再起動後も新パスワードを恒久保持したい場合は、ページ下部の「☁️ クラウド恒久保存」に表示されている最新コードを Streamlit Cloud の管理画面（Secrets）に貼り付けてください。")

        st.markdown("<div style='font-size:0.82rem; font-weight:700; color:#9A3412; margin:8px 0 2px 0;'>🔑 ① 一般ログインパスワードの変更（ご家族用）</div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:0.72rem; color:#78716C; margin:0 0 6px 0;'>ご家族に教える「閲覧用パスワード」を変更します。（※管理者パスワードは変わりません）</p>", unsafe_allow_html=True)
        with st.form("change_user_pwd_form", clear_on_submit=True):
            new_u_pwd = st.text_input("新しい一般ログインパスワード（4文字以上）", type="password", placeholder="新しいパスワード")
            new_u_pwd_conf = st.text_input("新しい一般ログインパスワード（再確認）", type="password", placeholder="新しいパスワードを再入力")
            update_u_btn = st.form_submit_button("一般ログインパスワードを更新する", use_container_width=True)

            if update_u_btn:
                if len(new_u_pwd) < MIN_PASSWORD_LENGTH:
                    st.error(f"❌ パスワードは{MIN_PASSWORD_LENGTH}文字以上で指定してください。")
                elif new_u_pwd != new_u_pwd_conf:
                    st.error("❌ 再確認用パスワードが一致しません。")
                else:
                    if update_user_password(new_u_pwd):
                        st.session_state["user_pwd_updated_notice"] = True
                        st.rerun()
                    else:
                        st.error("❌ パスワードの保存に失敗しました。")

        st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.82rem; font-weight:700; color:#9A3412; margin:8px 0 2px 0;'>🛡️ ② 管理者用マスターパスワードの変更（管理者様専用）</div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:0.72rem; color:#78716C; margin:0 0 6px 0;'>設定管理やURL再発行を行うための管理者専用パスワードを変更します。</p>", unsafe_allow_html=True)
        with st.form("change_admin_pwd_form", clear_on_submit=True):
            cur_a_pwd = st.text_input("現在の管理者パスワード", type="password", placeholder="現在の管理者パスワード")
            new_a_pwd = st.text_input("新しい管理者パスワード（4文字以上）", type="password", placeholder="新しい管理者パスワード")
            new_a_pwd_conf = st.text_input("新しい管理者パスワード（再確認）", type="password", placeholder="新しい管理者パスワードを再入力")
            update_a_btn = st.form_submit_button("管理者パスワードを更新する", use_container_width=True)

            if update_a_btn:
                if not credentials or not verify_admin_access(cur_a_pwd, credentials):
                    st.error("❌ 現在の管理者パスワードが正しくありません。")
                elif len(new_a_pwd) < MIN_PASSWORD_LENGTH:
                    st.error(f"❌ 新しいパスワードは{MIN_PASSWORD_LENGTH}文字以上で指定してください。")
                elif new_a_pwd != new_a_pwd_conf:
                    st.error("❌ 新しい管理者パスワードの再確認が一致しません。")
                else:
                    if update_admin_password(new_a_pwd):
                        st.session_state["admin_pwd_updated_notice"] = True
                        st.rerun()
                    else:
                        st.error("❌ パスワードの保存に失敗しました。")

        st.markdown("---")
        # セキュア・アクセストークンURL発行
        if credentials and "token" in credentials:
            token = credentials["token"]
            dynamic_url = generate_token_link(token)
            st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#44403C; margin-bottom:4px;'>🔗 安全なワンタップ起動URL（トークン方式）</div>", unsafe_allow_html=True)
            st.markdown("<p style='font-size:0.73rem; color:#78716C; margin-bottom:6px;'>ご家族に共有するための専用URLです。パスワード入力不要で安全に起動できます。</p>", unsafe_allow_html=True)

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
                    border: 1px solid #EADBC8;
                    border-radius: 12px;
                    padding: 6px 10px;
                    box-shadow: 0 1px 3px rgba(67,20,7,0.03);
                }}
                input {{
                    flex: 1;
                    border: none;
                    background: transparent;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.8rem;
                    color: #44403C;
                    outline: none;
                    width: 100%;
                }}
                button {{
                    padding: 8px 16px;
                    font-size: 0.8rem;
                    font-weight: 700;
                    color: white;
                    background: linear-gradient(135deg, #EA580C 0%, #F97316 100%);
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    white-space: nowrap;
                    box-shadow: 0 2px 8px rgba(234, 88, 12, 0.28);
                    transition: all 0.15s ease;
                }}
                button:hover {{
                    background: linear-gradient(135deg, #C2410C 0%, #EA580C 100%);
                    box-shadow: 0 4px 12px rgba(234, 88, 12, 0.38);
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
                        btn.style.background = '#EA580C';
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
            st.markdown("<div style='font-size:0.75rem; font-weight:600; color:#44403C; margin-bottom:4px;'>💡 現在開いているブラウザのアドレスから自動生成された共有URL:</div>", unsafe_allow_html=True)
            components.html(iframe_html, height=72)
            st.code(init_display_url, language="text")
            st.caption("※上のオレンジの「📋 コピー」ボタン、または右上のコピーアイコンを押すと、ご家族に送るURLが確実にコピーされます。")

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
                secrets_toml = get_secrets_toml_template(
                    credentials.get("user_hash", ""),
                    credentials.get("user_salt", ""),
                    credentials.get("admin_hash", ""),
                    credentials.get("admin_salt", ""),
                    credentials.get("token_salt")
                )
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
        st.markdown("<p style='font-size:0.75rem; color:#64748B; margin-bottom:8px;'>パスワード変更や共有URLの管理を行うには、管理者用マスターパスワードを入力してください。</p>", unsafe_allow_html=True)
        with st.form("admin_unlock_form", clear_on_submit=True):
            admin_input = st.text_input("管理者パスワード", type="password", placeholder="管理者専用パスワードを入力")
            admin_submit = st.form_submit_button("認証してロック解除 🔓", use_container_width=True, type="primary")

            if admin_submit:
                if credentials and verify_admin_access(admin_input, credentials):
                    st.session_state["is_admin"] = True
                    st.success("✅ 管理者認証に成功しました！")
                    st.rerun()
                else:
                    st.error("❌ 管理者パスワードが正しくありません。（一般ログインパスワードでは解除できません）")

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
<div style="text-align:center; color:#A8A29E; font-size:0.68rem; margin-top:16px; letter-spacing:0.02em; line-height:1.6;">
    KOIASA TRANSIT SYSTEM V4.0 ｜ 収録ダイヤ: {escape_text(revision_info.get('current_version', '2026年春季現行ダイヤ'))}<br>
    <span style="font-size:0.62rem; color:#D6D3D1;">※本アプリは所定時刻表に基づき計算しています。遅延・運休情報は各社公式リンクをご確認ください。</span>
</div>
""", unsafe_allow_html=True)


