import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time
import pytz  # 新增時區庫
from streamlit_calendar import calendar

# --- 1. 配置與數據庫 ---
DB_NAME = "work_master.db"
TZ = pytz.timezone('Asia/Shanghai') 

def get_now():
    return datetime.now(pytz.utc).astimezone(TZ)

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS attendance
                     (date TEXT PRIMARY KEY, start_time TEXT, end_time TEXT, 
                      actual_work REAL, overtime REAL)''')
        conn.commit()

# --- 2. 頁面配置 ---
st.set_page_config(page_title="工時 masters", page_icon="⏱️", layout="wide")
init_db()

# --- 3. 側邊欄：規則設定 ---
with st.sidebar:
    st.header("⚙️ 考勤規則")
    def_start = st.time_input("預設上班時間", time(8, 30))
    std_end = st.time_input("標準下班時間", time(18, 0))
    b_start = st.time_input("午休開始", time(12, 0))
    b_end = st.time_input("午休結束", time(13, 30))
    st.divider()
    if st.button("🗑️ 清空所有記錄", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM attendance")
        st.cache_data.clear()
        st.rerun()

# --- 4. 主功能分頁 ---
tab_record, tab_calendar = st.tabs(["⏱️ 快速打卡", "📅 歷史月歷"])

with tab_record:
    now = get_now()  # 使用修正後的東八區時間
    today_str = now.strftime("%Y-%m-%d")
    
    if 'today_start' not in st.session_state:
        st.session_state.today_start = def_start.strftime("%H:%M:%S")

    st.subheader(f"📅 今日：{today_str} (東八區)")
    
    c1, c2 = st.columns(2)
    if c1.button("☀️ 上班打卡", use_container_width=True):
        st.session_state.today_start = now.strftime("%H:%M:%S")
        st.rerun()

    if c2.button("🌙 下班打卡", type="primary", use_container_width=True):
        # 計算邏輯
        start_dt = TZ.localize(datetime.combine(now.date(), datetime.strptime(st.session_state.today_start, "%H:%M:%S").time()))
        bs_dt, be_dt, se_dt = [TZ.localize(datetime.combine(now.date(), t)) for t in [b_start, b_end, std_end]]
        
        # 判定扣除時長
        if now <= bs_dt:
            deduct = 0.0
        elif bs_dt < now <= be_dt:
            deduct = (now - bs_dt).total_seconds() / 3600
        else:
            deduct = (be_dt - bs_dt).total_seconds() / 3600
            
        work_h = round(max(0, (now - start_dt).total_seconds() / 3600 - deduct), 2)
        ot_h = round(max(0, (now - se_dt).total_seconds() / 3600), 2)

        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("REPLACE INTO attendance VALUES (?,?,?,?,?)",
                         (today_str, st.session_state.today_start, now.strftime("%H:%M:%S"), work_h, ot_h))
        st.cache_data.clear()
        st.success(f"打卡成功！工時 {work_h}h")
        st.balloons()
        st.rerun()

    st.info(f"當前記錄起點: {st.session_state.today_start}")

    # --- 歷史補錄 ---
    st.divider()
    with st.expander("📝 補錄或修改歷史記錄"):
        with st.form("manual_entry", clear_on_submit=True):
            m_date = st.date_input("選擇日期", now.date()) # 預設日期改為修正後的今天
            mc1, mc2 = st.columns(2)
            m_start = mc1.time_input("上班時間", time(8, 30))
            m_end = mc2.time_input("下班時間", time(18, 0))
            
            if st.form_submit_button("確認保存", use_container_width=True):
                # 補錄不需要實時時區轉換，直接用輸入日期即可
                m_start_dt = datetime.combine(m_date, m_start)
                m_end_dt = datetime.combine(m_date, m_end)
                m_bs_dt, m_be_dt, m_std_end = [datetime.combine(m_date, t) for t in [b_start, b_end, std_end]]

                m_deduct = (m_be_dt - m_bs_dt).total_seconds() / 3600 if m_end_dt > m_be_dt else 0
                m_work_h = round(max(0, (m_end_dt - m_start_dt).total_seconds() / 3600 - m_deduct), 2)
                m_ot_h = round(max(0, (m_end_dt - m_std_end).total_seconds() / 3600), 2)

                with sqlite3.connect(DB_NAME) as conn:
                    conn.execute("REPLACE INTO attendance VALUES (?,?,?,?,?)",
                                 (m_date.strftime("%Y-%m-%d"), m_start.strftime("%H:%M:%S"), 
                                  m_end.strftime("%H:%M:%S"), m_work_h, m_ot_h))
                st.cache_data.clear()
                st.success(f"{m_date} 記錄已更新")
                st.rerun()

# 月歷部分保持不變...
# (省略後續日歷顯示代碼，邏輯與之前一致)
