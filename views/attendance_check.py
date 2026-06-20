import streamlit as st
import pandas as pd
import time
from utils.g_sheets import (
    get_student_master,
    load_seating_data,
    save_seating_data
)
from utils.api_guard import robust_api_call

def safe_get_student_master():
    df = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def render_attendance_seat_page():
    st.header("🗺️ 本日の教室状況・座席管理")
    
    user_role = st.session_state.get('role', '')
    
    loading_progress = st.progress(0, text="☁️ クラウドからデータを読み込み中...")
    
    loading_progress.progress(30, text="📋 生徒名簿を確認中...")
    df_students = safe_get_student_master()
    
    student_options = []
    if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
        student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    time.sleep(0.2)
    
    loading_progress.progress(70, text="🪑 今日の座席表を広げています...")
    all_seating_data = robust_api_call(load_seating_data, fallback_value={})
    time.sleep(0.2)
    
    loading_progress.progress(100, text="✨ 読み込み完了！")
    time.sleep(0.5)
    loading_progress.empty()

    time_slots = [
        "Aコマ (9:30~)", "Bコマ (11:10~)", "0コマ (13:10~)", 
        "1コマ (14:50~)", "2コマ (16:40~)", "3コマ (18:20~)", "4コマ (20:00~)"
    ]
    
    can_edit_seat = user_role in ['admin', 'owner']
    
    if 'num_booths' not in st.session_state:
        st.session_state['num_booths'] = 6

    if can_edit_seat:
        c_add, c_sub, _ = st.columns([1, 1, 3])
        if c_add.button("➕ ブース追加"): 
            st.session_state['num_booths'] += 1
            st.rerun()
        if c_sub.button("➖ 削減") and st.session_state['num_booths'] > 1:
            st.session_state['num_booths'] -= 1
            st.rerun()

    tab_names = [slot.split(" ")[0] for slot in time_slots]
    tabs = st.tabs(tab_names)

    for slot_idx, slot_name in enumerate(time_slots):
        with tabs[slot_idx]:
            st.markdown(f"#### 🕒 {slot_name}")
            
            slot_data = {k.split("||")[1]: v for k, v in all_seating_data.items() if f"{slot_name}||" in str(k)}

            if can_edit_seat:
                new_seating_for_slot = {}
                for i in range(0, st.session_state['num_booths'], 3):
                    cols = st.columns(3)
                    for j in range(3):
                        idx = i + j
                        if idx < st.session_state['num_booths']:
                            booth_name = f"ブース{idx+1}"
                            with cols[j]:
                                with st.container(border=True):
                                    st.write(f"**{booth_name}**")
                                    current_info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                                    
                                    current_seat = current_info["生徒名"]
                                    if current_seat != "-- 空席 --" and " - " not in current_seat:
                                        matching_opt = next((opt for opt in student_options if opt.endswith(f" - {current_seat}")), None)
                                        if matching_opt:
                                            current_seat = matching_opt
                                    
                                    options = ["-- 空席 --"] + student_options
                                    safe_index = options.index(current_seat) if current_seat in options else 0
                                    
                                    sel_name = st.selectbox("生徒", options, 
                                                            index=safe_index,
                                                            key=f"sel_{slot_idx}_{idx}")
                                    
                                    st_options = ["出席", "遅刻", "欠席連絡あり"]
                                    sel_status = st.radio("状態", st_options, 
                                                          index=st_options.index(current_info["状態"]) if current_info["状態"] in st_options else 0,
                                                          horizontal=True, key=f"rad_{slot_idx}_{idx}")
                                    
                                    new_seating_for_slot[booth_name] = {"生徒名": sel_name, "状態": sel_status}

                if st.button(f"💾 {tab_names[slot_idx]}を保存", key=f"save_{slot_idx}"):
                    with st.spinner("保存中..."):
                        for b_name, info in new_seating_for_slot.items():
                            all_seating_data[f"{slot_name}||{b_name}"] = info
                        
                        success = robust_api_call(lambda: save_seating_data(all_seating_data), fallback_value=False)
                        
                        if success is not False:
                            st.success("保存完了！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("保存に失敗しました。時間をおいて再試行してください。")
            else:
                if not slot_data:
                    st.info("データがありません。")
                else:
                    for i in range(0, max(6, len(slot_data)), 3):
                        cols = st.columns(3)
                        for j in range(3):
                            idx = i + j
                            booth_name = f"ブース{idx+1}"
                            if idx < max(6, len(slot_data)):
                                with cols[j]:
                                    with st.container(border=True):
                                        info = slot_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                                        st.markdown(f"**{booth_name}**")
                                        if info["生徒名"] == "-- 空席 --":
                                            st.caption("-- 空席 --")
                                        else:
                                            display_name = info['生徒名'].split(" - ")[1] if " - " in info['生徒名'] else info['生徒名']
                                            color = "#28a745" if info["状態"]=="出席" else "#dc3545"
                                            st.markdown(f"### {display_name}")
                                            st.markdown(f"<span style='color:{color}'>{info['状態']}</span>", unsafe_allow_html=True)

    # ==========================================
    # 🚀 一括保存ボタン
    # ==========================================
    if can_edit_seat:
        st.divider()
        if st.button("💾 全コマの座席表をまとめて一括保存", type="primary", use_container_width=True):
            save_progress = st.progress(0, text="📦 全データを集計中...")
            
            new_all_data = {}
            total_steps = len(time_slots)
            
            for s_idx, s_name in enumerate(time_slots):
                save_progress.progress((s_idx + 1) / (total_steps + 1), text=f"📂 {s_name} のデータを整理中...")
                for b_idx in range(st.session_state['num_booths']):
                    b_name = f"ブース{b_idx+1}"
                    s_val = st.session_state.get(f"sel_{s_idx}_{b_idx}", "-- 空席 --")
                    r_val = st.session_state.get(f"rad_{s_idx}_{b_idx}", "出席")
                    new_all_data[f"{s_name}||{b_name}"] = {"生徒名": s_val, "状態": r_val}
                time.sleep(0.05)
            
            save_progress.progress(0.95, text="🚀 Googleスプレッドシートに送信中...（APIエラー回避待機含む☕）")
            success = robust_api_call(lambda: save_seating_data(new_all_data), fallback_value=False)
            
            if success is not False:
                save_progress.progress(100, text="✅ すべての保存が完了しました！")
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                st.error("保存に失敗しました。少し時間をおいてから再度お試しください。")