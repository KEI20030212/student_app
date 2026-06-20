import streamlit as st
import pandas as pd
import time
import datetime

from utils.g_sheets import (
    load_board_message,
    save_board_message,
    get_all_logs,      
    load_quiz_records  
)
from utils.api_guard import robust_api_call

def safe_get_all_logs():
    df = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def safe_load_quiz_records():
    df = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def render_home_page():
    st.header("📢 ホーム・連絡掲示板")
    
    user_role = st.session_state.get('role', '')

    # ==========================================
    # 🌟 管理者専用：URL抜け（小テスト未実施）の自動検知アラート
    # ==========================================
    if user_role in ['admin', 'owner', 'head_teacher']:
        df_logs = safe_get_all_logs() 
        df_quizzes = safe_load_quiz_records() 
        today = datetime.date.today()
        
        if not df_logs.empty and "APIエラー発生" not in df_logs.columns:
            df_logs['日時'] = pd.to_datetime(df_logs['日時'], format='mixed', errors='coerce')
            today_logs = df_logs[df_logs['日時'].dt.date == today]
            
            if not today_logs.empty:
                name_col = '名前' if '名前' in today_logs.columns else '生徒名'
                today_students = today_logs[name_col].drop_duplicates().tolist()
                
                missing_url_students = []
                for student in today_students:
                    has_quiz = False
                    if not df_quizzes.empty and "APIエラー発生" not in df_quizzes.columns:
                        df_quizzes['日時'] = pd.to_datetime(df_quizzes['日時'], format='mixed', errors='coerce')
                        student_quizzes = df_quizzes[(df_quizzes['名前'] == student) & (df_quizzes['日時'].dt.date == today)]
                        if not student_quizzes.empty:
                            has_quiz = True
                            
                    if not has_quiz:
                        missing_url_students.append(student)
                        
                if missing_url_students:
                    st.error(f"🚨 **【答案確認URL 未添付アラート】**\n\n本日授業記録がある以下の生徒は、小テスト結果が未登録のためLINE報告書にDriveのURLが添付されていません。画像アップロードと小テスト結果の登録漏れがないか確認してください。\n\n**{', '.join(missing_url_students)}**")

    st.divider()
    
    # ==========================================
    # 🌟 掲示板エリア
    # ==========================================
    st.subheader("📌 講師向け 連絡事項")
    
    board_data = robust_api_call(load_board_message, fallback_value={"message": "", "updated_at": "---"})
    current_message = board_data.get("message", "本日の連絡事項はありません。")
    updated_at = board_data.get("updated_at", "---")
    
    if updated_at and updated_at != "---":
        st.caption(f"🕒 最終更新日時: {updated_at}")
    
    st.info(current_message.replace('\n', '  \n'))
    
    if user_role in ['admin', 'owner', 'head_teacher']:
        with st.expander("✏️ 掲示板を編集"):
            new_msg = st.text_area("内容を入力", value=current_message, height=100)
            if st.button("💾 掲示板を更新"):
                with st.spinner("更新中..."):
                    success = robust_api_call(lambda: save_board_message(new_msg), fallback_value=False)
                    if success is not False:
                        load_board_message.clear()
                        st.success("更新しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("通信エラーにより更新できませんでした。")