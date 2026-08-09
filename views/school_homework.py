import streamlit as st
import pandas as pd
from utils.g_sheets import load_school_homework_data, get_student_master
from utils.api_guard import robust_api_call

# 🌟 新しく作った5つのファイルをインポート！
from views.school_hw_alert import render_hw_alert
from views.school_hw_add import render_hw_add
from views.school_hw_dash import render_hw_dash
from views.school_hw_edit import render_hw_edit
from views.school_hw_past import render_hw_past

def render_school_homework_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🎒 学校課題管理")
    with col_r:
        if st.button("🔄 情報を更新"):
            st.cache_data.clear() 
            st.rerun()

    # 🌟 超高速化：ここで1回だけデータを取得し、各タブに「配る」設計に変更！
    with st.spinner("データを読み込み中..."):
        df_hw = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
            
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録", "📊 進捗ダッシュボード", "🛠️ 課題の修正・管理", "📜 過去の課題・履歴検索"])

    with tab1:
        render_hw_alert(df_hw)
    with tab2:
        render_hw_add(df_students)
    with tab3:
        render_hw_dash(df_hw)
    with tab4:
        render_hw_edit(df_hw, df_students)
    with tab5:
        render_hw_past(df_hw, df_students)