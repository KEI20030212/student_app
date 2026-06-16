import streamlit as st
import pandas as pd # 🌟 DataFrameを使うために追加

from utils.g_sheets import (
    get_student_master,
    load_seating_data,
    save_seating_data
)

# 🌟 APIガードをインポート
from utils.api_guard import robust_api_call

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def render_attendance_seat_page():
    st.header("✅ 本日の出欠・座席管理")
    st.write("今日の授業の座席割り当てと、生徒の出欠状況を一画面で管理します。")
    
    # 🌟 1. 生徒マスターからID付きのリストを作成する
    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    student_options = []
    
    if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
        student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    if not student_options:
        st.warning("💡 生徒データが登録されていないか、通信エラーで取得できませんでした。")
        return
    
    # 🌟 2. 座席データの取得に robust_api_call を適用（失敗時は空の辞書を返す）
    seating_data = robust_api_call(load_seating_data, fallback_value={})
    
    if 'num_booths' not in st.session_state:
        st.session_state['num_booths'] = max(6, len(seating_data))

    st.subheader("🗺️ 教室レイアウト (座席表)")

    col_add, col_sub, _ = st.columns([1, 1, 3])
    with col_add:
        if st.button("➕ ブースを追加", use_container_width=True):
            st.session_state['num_booths'] += 1
            st.rerun()
    with col_sub:
        if st.button("➖ ブースを減らす", use_container_width=True):
            if st.session_state['num_booths'] > 1:
                st.session_state['num_booths'] -= 1
                st.rerun()
            else:
                st.warning("これ以上減らせません！")

    new_seating = {}
    
    # =========================================================
    # 🌟 現在「どこかのブース」にいる生徒をリストアップ！
    # =========================================================
    assigned_students = set()
    for i in range(st.session_state['num_booths']):
        key = f"seat_{i}"
        if key in st.session_state:
            # 画面上で今選ばれている生徒
            seat_val = st.session_state[key]
            if seat_val != "-- 空席 --":
                assigned_students.add(seat_val)
        else:
            # 初回読み込み時は、保存されているデータから拾う
            booth_name = f"ブース{i+1}"
            info = seating_data.get(booth_name, {"生徒名": "-- 空席 --"})
            if info.get("生徒名") != "-- 空席 --":
                # 🌟 古いデータ（名前のみ）が入っていた場合の自己修復ロジック
                saved_name = info["生徒名"]
                if " - " not in saved_name:
                    matching_opt = next((opt for opt in student_options if opt.endswith(f" - {saved_name}")), None)
                    if matching_opt:
                        saved_name = matching_opt
                
                assigned_students.add(saved_name)

    # =========================================================
    # 🌟 3つずつ行を作る作戦（選択肢のフィルター機能追加）
    # =========================================================
    for i in range(0, st.session_state['num_booths'], 3):
        cols = st.columns(3)
        
        for j in range(3):
            if i + j < st.session_state['num_booths']:
                booth_index = i + j
                booth_name = f"ブース{booth_index+1}"
                
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"**🪑 {booth_name}**")
                        
                        current_info = seating_data.get(booth_name, {"生徒名": "-- 空席 --", "状態": "出席"})
                        
                        # 最新の選択状況（セッションステート）があれば優先、なければデータから
                        current_seat = st.session_state.get(f"seat_{booth_index}", current_info["生徒名"])
                        current_status = st.session_state.get(f"status_{booth_index}", current_info["状態"])
                        
                        # 🌟 古いデータ（名前のみ）がセットされようとした場合の自己修復ロジック
                        if current_seat != "-- 空席 --" and " - " not in current_seat:
                            matching_opt = next((opt for opt in student_options if opt.endswith(f" - {current_seat}")), None)
                            if matching_opt:
                                current_seat = matching_opt
                        
                        # 🎯 選択肢をスマートに絞り込む！
                        options = ["-- 空席 --"]
                        for s in student_options:
                            # 「まだ誰にも選ばれていない生徒」 OR 「今このブースに座っている生徒」 だけを選択肢に入れる
                            if (s not in assigned_students) or (s == current_seat):
                                options.append(s)
                        
                        # 万が一 current_seat が options に無い場合のエラー回避
                        safe_index = options.index(current_seat) if current_seat in options else 0

                        new_occupant = st.selectbox(
                            "生徒名", 
                            options, 
                            index=safe_index, 
                            key=f"seat_{booth_index}"
                        )
                        
                        if new_occupant != "-- 空席 --":
                            status_options = ["出席", "遅刻", "欠席連絡あり"]
                            safe_status_index = status_options.index(current_status) if current_status in status_options else 0
                            
                            new_status = st.radio(
                                "状態", 
                                status_options, 
                                index=safe_status_index,
                                horizontal=True, 
                                key=f"status_{booth_index}"
                            )
                        else:
                            new_status = "出席" 
                            
                        new_seating[booth_name] = {"生徒名": new_occupant, "状態": new_status}
    
    st.divider()
    if st.button("💾 本日の座席表を確定・共有する", type="primary", use_container_width=True):
        with st.spinner('☁️ スプレッドシートに保存中...（混雑時は自動で再試行します）'):
            
            # 🌟 3. 保存処理を関数で包んで robust_api_call に渡す
            def _save():
                save_seating_data(new_seating)
                return True
                
            success = robust_api_call(_save, fallback_value=False)
            
            if success:
                st.session_state['num_booths'] = len(new_seating)
                st.success(f"✨ 全 {len(new_seating)} ブースの座席表をクラウドに保存しました！")
                st.rerun()
            else:
                st.error("保存に失敗しました。少し時間をおいてから再度お試しください。")