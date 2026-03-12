import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time
from streamlit_calendar import calendar

# --- 1. 数据库逻辑 (保持不变) ---
DB_NAME = "work_master.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS attendance
                     (date TEXT PRIMARY KEY, 
                      start_time TEXT, 
                      end_time TEXT, 
                      actual_work REAL, 
                      overtime REAL)''')
        conn.commit()

COLUMN_MAP = {"date": "日期", "start_time": "上班", "end_time": "下班", "actual_work": "工时", "overtime": "加班"}

@st.cache_data(ttl=60)
def get_calendar_events():
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM attendance", conn)
    events = []
    for _, row in df.iterrows():
        is_ot = row['overtime'] > 0
        events.append({
            "title": f"{'🚨' if is_ot else '✅'} {row['actual_work']}h",
            "start": row['date'],
            "end": row['date'],
            "backgroundColor": "#FF4B4B" if is_ot else "#00C851",
            "borderColor": "#FF4B4B" if is_ot else "#00C851",
            "display": "block"
        })
    return events

# --- 2. 页面配置 ---
st.set_page_config(page_title="工时大师", page_icon="⏱️", layout="wide")
init_db()

# --- 3. 侧边栏：规则设定 ---
with st.sidebar:
    st.header("⚙️ 考勤规则")
    def_start = st.time_input("默认上班", time(8, 30))
    std_end = st.time_input("标准下班", time(18, 0))
    b_start = st.time_input("午休开始", time(12, 0))
    b_end = st.time_input("午休结束", time(13, 30))
    st.divider()
    if st.button("🗑️ 清空记录", type="secondary", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM attendance")
        st.cache_data.clear()
        st.rerun()

# --- 4. 移动端优化布局：使用 Tabs ---
tab_record, tab_calendar = st.tabs(["⏱️ 打卡 & 补录", "📅 工作月历"])

# --- TAB 1: 打卡与补录 ---
with tab_record:
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    if 'today_start' not in st.session_state:
        st.session_state.today_start = def_start.strftime("%H:%M:%S")

    st.subheader(f"📅 今日：{today_str}")
    
    # 打卡按钮排布
    c1, c2 = st.columns(2)
    if c1.button("☀️ 上班打卡", use_container_width=True):
        st.session_state.today_start = now.strftime("%H:%M:%S")
        st.rerun()

    if c2.button("🌙 下班打卡", type="primary", use_container_width=True):
        # 逻辑复用
        start_dt = datetime.combine(now.date(), datetime.strptime(st.session_state.today_start, "%H:%M:%S").time())
        bs_dt, be_dt, se_dt = [datetime.combine(now.date(), t) for t in [b_start, b_end, std_end]]
        
        deduct = 0.0
        if now > bs_dt:
            deduct = (min(now, be_dt) - bs_dt).total_seconds() / 3600 if now <= be_dt else (be_dt - bs_dt).total_seconds() / 3600
            
        work_h = round(max(0, (now - start_dt).total_seconds() / 3600 - deduct), 2)
        ot_h = round(max(0, (now - se_dt).total_seconds() / 3600), 2)

        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("REPLACE INTO attendance VALUES (?,?,?,?,?)",
                         (today_str, st.session_state.today_start, now.strftime("%H:%M:%S"), work_h, ot_h))
        st.cache_data.clear()
        st.success(f"已打卡：{work_h}h")
        st.rerun()

    st.info(f"今日上班起点: {st.session_state.today_start}")

    # 历史补录 - 针对手机优化，减少嵌套
    st.divider()
    with st.expander("📝 补录历史数据"):
        with st.form("manual_entry", clear_on_submit=True):
            m_date = st.date_input("补录日期", datetime.now())
            m_start = st.time_input("上班时间", time(8, 30))
            m_end = st.time_input("下班时间", time(18, 0))
            
            if st.form_submit_button("确认保存", use_container_width=True):
                # 补录计算
                m_start_dt = datetime.combine(m_date, m_start)
                m_end_dt = datetime.combine(m_date, m_end)
                m_bs_dt, m_be_dt, m_std_end = [datetime.combine(m_date, t) for t in [b_start, b_end, std_end]]

                m_deduct = (m_be_dt - m_bs_dt).total_seconds() / 3600 if m_end_dt > m_be_dt else 0
                m_work_h = round(max(0, (m_end_dt - m_start_dt).total_seconds() / 3600 - m_deduct), 2)
                m_ot_h = round(max(0, (m_end_dt - m_std_end).total_seconds() / 3600), 2)

                with sqlite3.connect(DB_NAME) as conn:
                    conn.execute("REPLACE INTO attendance VALUES (?,?,?,?,?)",
                                 (m_date.strftime("%Y-%m-%d"), m_start.strftime("%H:%M:%S"), m_end.strftime("%H:%M:%S"), m_work_h, m_ot_h))
                st.cache_data.clear()
                st.success("补录成功")
                st.rerun()

# --- TAB 2: 月历视图 ---
with tab_calendar:
    # 缩小手机端月历高度
    events = get_calendar_events()
    calendar(
        events=events,
        options={
            "initialView": "dayGridMonth",
            "locale": "zh-cn",
            "height": 450, # 手机端更紧凑的高度
            "headerToolbar": {"left": "prev,next", "center": "title", "right": "today"}
        }
    )
    
    # 底部简易数据表
    with sqlite3.connect(DB_NAME) as conn:
        recent_df = pd.read_sql_query("SELECT * FROM attendance ORDER BY date DESC LIMIT 5", conn)
    if not recent_df.empty:
        st.write("📊 **近期数据**")
        st.dataframe(recent_df.rename(columns=COLUMN_MAP), hide_index=True, use_container_width=True)
