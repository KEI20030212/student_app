import streamlit as st

from views.dashboard import render_dashboard_page
from views.self_study_dashboard import render_self_study_dashboard
from views.test_score_list import render_test_scores_list_page

def render_combined_dashboard_page():
    st.header("🏫 教室・学習状況ダッシュボード")
    
    tab1, tab2 ,tab3 = st.tabs(["🌐 クラス全体ダッシュボード", "📊 自習時間ランキング", "📝 成績一覧表"])
    
    with tab1:
        render_dashboard_page()
        
    with tab2:
        render_self_study_dashboard()
        
    with tab3:
        render_test_scores_list_page()