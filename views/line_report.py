import streamlit as st
from views.line_report_generate import render_report_generation_tab
from views.line_report_reply import render_parent_reply_tab
from views.line_parent_reply_dashboard import render_parent_reply_dashboard
from views.line_monthly_report import render_monthly_visual_report_tab
from views.email_report_generate import render_email_report_tab

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

    if can_use_reply:
        # 🌟 修正：タブを「4つ」に増やしました！
        main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
            "📱 LINEレポート一括生成",
            "📧 メール送信用レポート生成",
            "💬 保護者返信・ファン化度記録", 
            "📂 過去の返信アーカイブ",
            "🖼️ 月末ビジュアルレポート生成" # 👈 これが新しい機能です！
        ])
        
        with main_tab1:
            render_report_generation_tab(can_use_report)
        with main_tab2:
            render_email_report_tab(can_use_report)
        with main_tab3:
            render_parent_reply_tab()
        with main_tab4:
            render_parent_reply_dashboard()
        with main_tab5:
            render_monthly_visual_report_tab()
    else:
        render_report_generation_tab(can_use_report)