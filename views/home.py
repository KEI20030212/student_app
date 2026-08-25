import streamlit as st

from views.board import render_home_page
#from views.attendance_check import render_attendance_seat_page
from views.feedback_all_board import render_feedback_all_board

def render_combined_home_page():
    st.header("📢 ホーム")

    record_type = st.radio(
        "確認事項を選択してください", 
        ["📢 連絡掲示板", "📩 フィードバック一覧"], 
        horizontal=True, 
        key="record_type_combined"
    )
    st.divider()

    if record_type == "📢 連絡掲示板":
        render_home_page()
    #elif record_type == "🗺️ 本日の教室状況・座席管理":
        #render_attendance_seat_page()    
    elif record_type == "📩 フィードバック一覧":
        render_feedback_all_board()