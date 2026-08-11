import streamlit as st
# 🌟 分割した子ファイルを呼び出す
from views.line_report_generate import render_report_generation_tab
from views.line_report_reply import render_parent_reply_tab
from views.line_parent_reply_dashboard import render_parent_reply_dashboard

def render_line_report_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("📱 LINE用 授業報告レポート管理")
    with col_r:
        if st.button("🔄 データを更新", use_container_width=True):
            st.cache_data.clear() 
            st.rerun()            
    
    user_role = st.session_state.get('role', '')
    
    can_use_report = user_role in ['admin', 'owner', 'am', 'head_teacher']
    can_use_reply = user_role in ['admin', 'owner', 'am']

    if not can_use_report and not can_use_reply:
        st.error("🔒 このページへのアクセス権限がありません。管理者または教室長（社員）のみ利用可能です。")
        st.stop()

    # 権限に応じてタブを分けるか、そのまま表示するかをコントロール
    if can_use_reply:
        main_tab1, main_tab2, main_tab3 = st.tabs(["📱 LINEレポート一括生成", "💬 保護者返信・ファン化度記録", "📂 過去の返信アーカイブ"])
        with main_tab1:
            render_report_generation_tab(can_use_report)
        with main_tab2:
            render_parent_reply_tab()
        with main_tab3:
            render_parent_reply_dashboard()
    else:
        # 教室長などの場合はタブを作らずにレポート生成だけ表示
        render_report_generation_tab(can_use_report)