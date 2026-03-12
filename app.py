import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time, timedelta
import pytz
from streamlit_calendar import calendar

# --- 1. 基础配置与时区设定 ---
DB_NAME = "work_master.db"
# 强制指定东八区时区
CHINA_TZ = pytz.timezone('Asia/Shanghai')

def get_now():
    """获取东八区当前的 datetime"""
    return datetime.now(pytz.utc).astimezone(CHINA_TZ)

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

# 中英映射
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
    def_start = st.time_input("默认上班时间", time(8, 30))
    std_end = st.time_input("标准下班时间", time(18, 0))
    st.subheader("☕ 午休时段")
    b_start = st.time_input("开始", time(12, 0))
    b_end = st.time_input("结束", time(13, 30))
    st.divider()
    if st.button("🗑️ 清空所有记录", type="secondary", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM attendance")
        st.cache_data.clear()
        st.rerun()
    st.caption("提示：时区已锁定为北京时间(GMT+8)")

# --- 4. 移动端适配布局：使用 Tabs 切换 ---
tab_record, tab_calendar = st.tabs(["⏱️ 快速打卡", "📅 历史月历"])

# --- TAB 1: 打卡与补录 ---
with tab_record:
    now = get_now()
    today_str = now.strftime("%Y-%m-%d")
    
    # 初始化 session_state
    if 'today_start' not in st.session_state:
        st.session_state.today_start = def_start.strftime("%H:%M:%S")

    st.subheader(f"📅 今日：{today_str}")
    
    # 打卡按钮布局
    c1, c2 = st.columns(2)
    if c1.button("☀️ 上班打卡", use_container_width=True):
        st.session_state.today_start = now.strftime("%H:%M:%S")
        st.rerun()

    if c2.button("🌙 下班打卡", type="primary", use_container_width=True):
        # 核心逻辑：时区感知的时间计算
        # 将 start_time 字符串转回带时区的 datetime
        start_time_obj = datetime.strptime(st.session_state.today_start, "%H:%M:%S").time()
        start_dt = CHINA_TZ.localize(datetime.combine(now.date(), start_time_obj))
        
        bs_dt, be_dt, se_dt = [CHINA_TZ.localize(datetime.combine(now.date(), t)) for t in [b_start, b_end, std_end]]
        
        # 判定扣除时长
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
        st.success(f"打卡成功！今日工时 {work_h}h")
        st.balloons()
        st.rerun()

    st.info(f"当前记录起点: {st.session_state.today_start}")

    # --- 历史补录 ---
    st.divider()
    with st.expander("📝 补录或修改历史记录"):
        with st.form("manual_entry", clear_on_submit=True):
            m_date = st.date_input("选择日期", now.date())
            mc1, mc2 = st.columns(2)
            m_start = mc1.time_input("上班时间", time(8, 30))
            m_end = mc2.time_input("下班时间", time(18, 0))
            
            if st.form_submit_button("确认保存", use_container_width=True):
                # 补录计算逻辑
                m_start_dt = datetime.combine(m_date, m_start)
                m_end_dt = datetime.combine(m_date, m_end)
                m_bs_dt, m_be_dt, m_std_end = [datetime.combine(m_date, t) for t in [b_start, b_end, std_end]]

                m_deduct = (m_be_dt - m_bs_dt).total_seconds() / 3600 if m_end_dt > m_be_dt else 0
                m_work_h = round(max(0, (m_end_dt - m_start_dt).total_seconds() / 3600 - m_deduct), 2)
                m_ot_h = round(max(0, (m_end_dt - m_std_end).total_seconds() / 3600), 2)

                with sqlite3.connect(DB_NAME) as conn:
                    conn.execute("REPLACE INTO attendance VALUES (?,?,?,?,?)",
                                 (m_date.strftime("%Y-%m-%d"), 
                                  m_start.strftime("%H:%M:%S"), 
                                  m_end.strftime("%H:%M:%S"), 
                                  m_work_h, m_ot_h))
                st.cache_data.clear()
                st.success(f"{m_date} 记录已更新")
                st.rerun()

# --- TAB 2: 月历视图 ---
with tab_calendar:
    st.subheader("📅 工作月历")
    events = get_calendar_events()
    calendar(
        events=events,
        options={
            "initialView": "dayGridMonth",
            "locale": "zh-cn",
            "height": 480,
            "headerToolbar": {"left": "prev,next", "center": "title", "right": "today"}
        }
    )
    
    st.divider()
    with sqlite3.connect(DB_NAME) as conn:
        all_df = pd.read_sql_query("SELECT * FROM attendance ORDER BY date DESC LIMIT 5", conn)
    if not all_df.empty:
        st.write("📊 **最近记录**")
        st.dataframe(all_df.rename(columns=COLUMN_MAP), hide_index=True, use_container_width=True)
        
        csv_df = pd.read_sql_query("SELECT * FROM attendance ORDER BY date DESC", conn)
        csv = csv_df.rename(columns=COLUMN_MAP).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出全量数据 (CSV)", csv, "work_log.csv", "text/csv", use_container_width=True)
