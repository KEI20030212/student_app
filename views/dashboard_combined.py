import streamlit as st

# 完成している2つのファイルを部品として読み込む
from views.dashboard import render_dashboard_page
from views.self_study_dashboard import render_self_study_dashboard

def render_combined_dashboard_page():
    st.header("🏫 教室・学習状況ダッシュボード")
    
    # タブを作成
    tab1, tab2 = st.tabs(["🌐 クラス全体ダッシュボード", "📊 自習時間ランキング"])
    
    with tab1:
        render_dashboard_page()
        
    with tab2:
        render_self_study_dashboard()