import streamlit as st

from views.board import render_home_page
#from views.attendance_check import render_attendance_seat_page
from views.messages import render_messages_page

def render_combined_home_page():
    st.header("📢 ホーム")

    record_type = st.radio(
        "確認事項を選択してください", 
        ["📢 連絡掲示板", "💌 あなた宛てのメッセージ"], 
        horizontal=True, 
        key="record_type_combined"
    )
    st.divider()

    if record_type == "📢 連絡掲示板":
        render_home_page()
    #elif record_type == "🗺️ 本日の教室状況・座席管理":
        #render_attendance_seat_page()    
    elif record_type == "💌 あなた宛てのメッセージ":
        render_messages_page()