"""
恋朝トレインタイマー (Koiasa Train Timer)
恋ヶ窪 ⇔ 朝霞台 リアルタイム電車ナビゲーション・ダッシュボード
Streamlit Webアプリケーション（地中海オーシャンブルー × すりガラスUI版）
"""

import streamlit as st
import datetime
import html
import urllib.parse
from typing import Optional

from transit_engine import get_routes, escape_text, is_safe_url
from timetable_data import LINE_INFO

# Streamlitページ基本設定（モバイル・レスポンシブ最適化）
st.set_page_config(
    page_title="恋朝トレインタイマー | 恋ヶ窪 ⇔ 朝霞台",
    page_icon="🚆",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 地中海オーシャンブルー × すりガラス調 スタイリング
st.markdown("""
<style>
    /* フォント設定 */
    html, body, [class*="css"] {
        font-family: "Inter", "Hiragino Sans", "Meiryo", sans-serif;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 580px;
    }
    /* ヘッダーカード */
    .ocean-header {
        background: linear-gradient(135deg, #004B73 0%, #0071A4 50%, #002F4A 100%);
        color: #FFFFFF;
        padding: 20px 24px;
        border-radius: 24px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px -4px rgba(0, 75, 115, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    /* メトリックカード（ニューモーフィズム・すりガラス） */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 16px 18px;
        border-radius: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 16px -2px rgba(0, 75, 115, 0.06);
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 800;
        color: #004B73;
        font-size: 1.8rem !important;
    }
    /* タイムラインステップカード */
    .leg-card {
        background: #FFFFFF;
        border-radius: 18px;
        padding: 14px 16px;
        margin: 8px 0;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
    }
    /* ボタンデザイン */
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

# ヘッダー表示
now = datetime.datetime.now()
time_str = now.strftime("%H:%M:%S")
date_str = now.strftime("%Y年%m月%d日")

st.markdown(f"""
<div class="ocean-header">
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <div>
            <div style="font-size:0.75rem; font-weight:700; letter-spacing:0.1em; opacity:0.8; text-transform:uppercase;">
                Realtime Transit Dashboard
            </div>
            <h1 style="margin:4px 0 2px 0; font-size:1.6rem; font-weight:900; color:white; letter-spacing:-0.02em;">
                恋朝トレインタイマー
            </h1>
            <p style="margin:0; font-size:0.85rem; opacity:0.9;">恋ヶ窪 ⇔ 朝霞台 リアルタイム発着予測</p>
        </div>
        <div style="text-align:right;">
            <div style="background:rgba(255,255,255,0.18); padding:4px 12px; border-radius:12px; font-size:0.75rem; font-weight:700; display:inline-block; border:1px solid rgba(255,255,255,0.25);">
                ● 平常運行
            </div>
            <div style="font-family:'JetBrains Mono', monospace; font-size:0.85rem; font-weight:700; margin-top:4px;">
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
    now=now
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

# 乗り継ぎルート詳細（タイムライン）
st.markdown("### 🗺️ 乗り継ぎルート詳細")

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
            <div style="font-weight:800; font-size:1.05rem; color:#0F172A;">
                {from_st} <span style="font-family:'JetBrains Mono'; color:#004B73; font-size:1.1rem; margin-left:6px;">{f_time} 発</span>
                <span style="font-size:0.75rem; color:#64748B; background:#F1F5F9; padding:2px 6px; border-radius:6px; margin-left:6px;">{platform}</span>
            </div>
            <div style="font-size:0.8rem; font-weight:700; color:{color};">
                乗車 {duration}分
            </div>
        </div>
        <div style="font-size:0.85rem; font-weight:700; color:{color}; margin-bottom:4px;">
            🚆 {line_name}（{dest}）
        </div>
        <div style="font-size:0.75rem; color:#64748B;">
            💡 {note}
        </div>
        <div style="margin-top:6px; font-weight:800; font-size:1.05rem; color:#0F172A;">
            ➡ {to_st} <span style="font-family:'JetBrains Mono'; color:#059669; font-size:1.1rem; margin-left:6px;">{t_time} 着</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 乗り換え待ち時間の案内
    if idx < len(current_route["legs"]) - 1 and wait_m > 0:
        badge = "✨ スムーズ接続" if wait_m <= 4 else f"待ち時間 {wait_m}分"
        st.markdown(f"""
        <div style="margin:-2px 0 4px 20px; font-size:0.78rem; font-weight:700; color:#0071A4;">
            ⬇️ 乗り換え待ち: 約 <strong>{wait_m}</strong> 分 ({badge})
        </div>
        """, unsafe_allow_html=True)

# その後の電車候補（比較・選択）
if len(routes) > 1:
    st.markdown("### 📑 その後の電車候補")
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
            st.markdown(f"<span style='color:#059669; font-weight:700;'>● {escape_text(line['status'])}</span>", unsafe_allow_html=True)
        with col_link:
            if is_safe_url(line['url']):
                st.markdown(f"[公式運行情報 ↗]({line['url']})")

# 更新ボタン
st.markdown("---")
if st.button("🔄 最新の時刻で再計算・更新", use_container_width=True):
    st.rerun()

# フッター
st.markdown("""
<div style="text-align:center; color:#94A3B8; font-size:0.75rem; margin-top:20px;">
    恋朝トレインタイマー © 2026<br>
    東証公式J-Quantsスクリーナー統一アーキテクチャ準拠
</div>
""", unsafe_allow_html=True)
