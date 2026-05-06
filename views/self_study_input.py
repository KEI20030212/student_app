import streamlit as st
import datetime
import time
import pandas as pd

from utils.g_sheets import (
    get_student_master,
    save_self_study_record
)
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def render_self_study_input_page():
    st.header("📝 自習記録の入力")
    
    # マスターデータ取得
    student_df = cached_get_student_master()
    if not student_df.empty:
        student_options = (student_df['生徒ID'].astype(str) + " - " + student_df['生徒名']).tolist()
    else:
        student_options = []
        st.warning("生徒データが取得できませんでした。")

    with st.container(border=True):
        st.write("📚 **自習記録の入力（一括登録モード）**")
        
        ss_options = ["🆕 新規登録"] + student_options
        ss_name = st.selectbox("👤 生徒を選択", ss_options, index=None, placeholder="生徒を選択", key="ss_name")
        
        if ss_name == "🆕 新規登録": 
            ss_name = st.text_input("新しい生徒の名前", key="ss_new_name")
        
        if ss_name:
            num_days = st.number_input("🗓️ 登録する日数", min_value=1, max_value=14, value=1, key="ss_num_days")
            st.divider()
            
            ss_records = []
            total_earned_points = 0
            
            for d in range(int(num_days)):
                st.write(f"**【 {d+1}日目の記録 】**")
                col_d, col_s, col_e, col_b = st.columns([1.5, 1.2, 1.2, 1])
                
                default_date = datetime.date.today() - datetime.timedelta(days=d)
                ss_date = col_d.date_input("📅 日付", default_date, key=f"d_{d}")
                
                s_time = col_s.time_input("🛫 開始", datetime.time(17, 0), key=f"s_{d}")
                e_time = col_e.time_input("🛬 終了", datetime.time(19, 0), key=f"e_{d}")
                b_min = col_b.number_input("☕ 休憩(分)", min_value=0, value=0, step=5, key=f"b_{d}")
                
                start_dt = datetime.datetime.combine(ss_date, s_time)
                end_dt = datetime.datetime.combine(ss_date, e_time)
                diff_min = (end_dt - start_dt).seconds // 60
                if end_dt < start_dt: 
                    diff_min = 0
                    
                actual_min = max(0, diff_min - b_min)
                pts = int(actual_min // 30) 
                total_earned_points += pts
                
                st.caption(f"⏱️ 滞在: {diff_min}分 ／ 🔥 実質勉強時間: **{actual_min}分** （獲得: {pts}pt）")
                ss_memo = st.text_area("📖 学習内容（テキスト名など）", height=70, key=f"m_{d}")
                
                ss_records.append({
                    "date": ss_date, "start": s_time, "end": e_time, 
                    "break": b_min, "actual": actual_min, "content": ss_memo, "pts": pts
                })
                st.divider()
            
            if st.button(f"💾 {num_days}日分のデータを安全に保存する", type="primary", use_container_width=True):
                with st.status("Googleスプレッドシートに送信中...", expanded=True) as status:
                    success_count = 0
                    
                    pure_name = ss_name.split(" - ")[1] if " - " in ss_name else ss_name

                    for idx, rec in enumerate(ss_records):
                        ok, msg = robust_api_call(
                            save_self_study_record,
                            rec["date"], pure_name, rec["start"], rec["end"], 
                            rec["break"], rec["actual"], rec["content"], rec["pts"],
                            fallback_value=(False, "エラー")
                        )
                        if ok:
                            success_count += 1
                            if idx < len(ss_records) - 1:
                                time.sleep(2)
                        else:
                            st.error(f"❌ {idx+1}件目でエラー: {msg}")
                            break 
                            
                    if success_count == len(ss_records):
                        status.update(label="すべて正常に保存されました！", state="complete", expanded=False)
                        st.success(f"✅ {pure_name}さんの{success_count}日分の記録を保存！ 合計 {total_earned_points}pt 獲得！")
                        st.cache_data.clear() 
                        st.balloons()
                        time.sleep(2)
                        
                        for k in list(st.session_state.keys()):
                            if k.startswith(("d_","s_","e_","b_","m_","ss_")): del st.session_state[k]
                        st.rerun()