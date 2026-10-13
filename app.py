# app.py

import streamlit as st
from PIL import Image
# ==========================================
# 📦 1. 画面部隊（views）のインポート
# ==========================================
from views.home import render_combined_home_page
from views.attendance_seat import render_attendance_seat_page
from views.multi_input import render_multi_input_page
from views.input_combined import render_combined_input_page
from views.student_portal import render_student_portal_page
from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
from views.dashboard_combined import render_combined_dashboard_page
from views.quiz_management import render_quiz_management_page
from views.school_homework import render_school_homework_page
from views.line_report import render_line_report_page
from views.search_page import render_search_page
from views.analytics_dashboard import render_analytics_dashboard_page
from views.my_salary import render_my_salary_page
from views.account_manager import render_account_manager_page
from views.finance_integrated import render_finance_integrated_page

# ==========================================
# 🛠️ 2. 裏方部隊（utils）のインポート
# ==========================================
from utils.calc_logic import calculate_hw_rate, calculate_quiz_points, calculate_motivation_rank
from utils.g_sheets import (
    get_textbook_master, 
    add_new_textbook, 
    get_last_homework_info,
    get_all_accounts,
    load_system_settings,
    save_system_settings
)
from utils.api_guard import robust_api_call

# ページの基本設定
try:
    img = Image.open("icon.jpg")
    st.set_page_config(page_title="管理システムK-AI", page_icon=img, layout="wide")
except Exception:
    st.set_page_config(page_title="管理システムK-AI", page_icon="🏫", layout="wide")

# --------------------------------------------------
# 🔒 初回セットアップ ＆ ログイン画面
# --------------------------------------------------
def login_screen():
    settings = robust_api_call(load_system_settings, fallback_value={})
    
    # 🌟 もし「教室長名」が設定されていなければ、初回セットアップ画面を表示
    if not settings or not settings.get("教室長名"):
        st.markdown("<h1 style='text-align: center; color: #FF4500;'>🚀 システム初回セットアップ</h1>", unsafe_allow_html=True)
        st.info("ようこそ！まずはこのシステムを利用する基本設定を行ってください。\n\n※複数校舎を管理する場合は「校舎2」「校舎3」も入力してください。（1校舎のみの場合は空欄でOKです）")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("setup_form"):
                setup_manager = st.text_input("👤 あなたのお名前（教室長名 / 代表者名）", placeholder="例：山田 太郎")
                st.caption("※ここで設定したお名前は、LINEレポートなどの自動署名に使用されます。")
                
                st.divider()
                st.markdown("### 🏢 校舎と生徒IDの設定")
                
                # 🌟 校舎1（必須）
                c1_1, c1_2 = st.columns([2, 1])
                setup_b1 = c1_1.text_input("🏫 メイン校舎名（必須）", placeholder="例：田端新町校")
                setup_p1 = c1_2.text_input("🔑 ID頭文字（必須）", placeholder="例：t")
                
                # 🌟 校舎2（任意）
                c2_1, c2_2 = st.columns([2, 1])
                setup_b2 = c2_1.text_input("🏫 校舎2（任意）", placeholder="例：東十条駅前校")
                setup_p2 = c2_2.text_input("🔑 ID頭文字（任意）", placeholder="例：h")
                
                # 🌟 校舎3（任意）
                c3_1, c3_2 = st.columns([2, 1])
                setup_b3 = c3_1.text_input("🏫 校舎3（任意）", placeholder="例：池上校")
                setup_p3 = c3_2.text_input("🔑 ID頭文字（任意）", placeholder="例：i")
                
                submit_setup = st.form_submit_button("設定を保存してシステムを開始 🚀", use_container_width=True)
                
                if submit_setup:
                    if setup_manager and setup_b1 and setup_p1:
                        # 入力された校舎情報を「校舎名:頭文字」のカンマ区切りにまとめる
                        branches = [f"{setup_b1}:{setup_p1}"]
                        if setup_b2 and setup_p2: branches.append(f"{setup_b2}:{setup_p2}")
                        if setup_b3 and setup_p3: branches.append(f"{setup_b3}:{setup_p3}")
                        
                        # まとめた文字列（例 "田端新町校:T, 東十条駅前校:H, 池上校:I"）を作る
                        combined_branches = ", ".join(branches)
                        
                        with st.spinner("スプレッドシートに設定を保存しています..."):
                            # save_system_settings は (manager_name, branch_name, id_prefix) を受け取る仕様なので、
                            # combined_branches を branch_name として保存し、prefix は一旦メインのものを渡す
                            success = robust_api_call(save_system_settings, setup_manager, combined_branches, setup_p1, fallback_value=False)
                            if success:
                                st.success("✅ 設定が完了しました！自動的にログインします。")
                                st.session_state.update({
                                    'logged_in': True, 
                                    'role': 'admin', 
                                    'username': setup_manager, 
                                    'user_id': 'admin',
                                    'sys_branch': combined_branches,
                                    'sys_prefix': setup_p1
                                })
                                st.rerun()
                            else:
                                st.error("❌ 保存に失敗しました。Googleスプレッドシートの連携を確認してください。")
                    else:
                        st.warning("「教室長名」「メイン校舎名」「ID頭文字」は必ず入力してください。")
        return 

    # 🌟 設定が完了している場合は、通常のログイン画面を表示
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>🌟 管理システムK-AI</h1>", unsafe_allow_html=True)
    
    # 登録されている校舎を綺麗に表示
    saved_branches = settings.get('メイン校舎名', '未設定')
    display_text = " / ".join([b.split(':')[0] for b in saved_branches.split(', ')]) if ':' in saved_branches else saved_branches
    st.markdown(f"<p style='text-align: center;'>登録校舎: <b>{display_text}</b></p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("👤 ユーザーID", autocomplete="username")
            password = st.text_input("🔑 パスワード", type="password", autocomplete="current-password")
            submit = st.form_submit_button("ログイン 🚀", use_container_width=True)
            
            if submit:
                # 緊急バックドア
                if username == "admin" and password == "admin123":
                    st.session_state.update({
                        'logged_in': True, 
                        'role': 'admin', 
                        'username': settings.get("教室長名", "管理者"), 
                        'user_id': 'admin',
                        'sys_branch': settings.get("メイン校舎名", ""),
                        'sys_prefix': settings.get("生徒IDの頭文字", "")
                    })
                    st.rerun()
                else:
                    accounts = robust_api_call(get_all_accounts, fallback_value={})

                    if username in accounts and str(accounts[username].get('パスワード')) == str(password):
                        st.session_state.update({
                            'logged_in': True, 
                            'role': accounts[username].get('権限', 'teacher'),
                            'username': accounts[username].get('講師名', accounts[username].get('名前', '先生')),
                            'user_id': username,
                            'sys_branch': settings.get("メイン校舎名", ""),
                            'sys_prefix': settings.get("生徒IDの頭文字", "")
                        })
                        st.rerun()
                    else:
                        st.error("⚠️ IDまたはパスワードが間違っています。")

# --------------------------------------------------
# 🚀 メイン画面＆ルーティング（司令塔）
# --------------------------------------------------
def main():
    if not st.session_state.get('logged_in', False):
        login_screen()
        return

    # 全画面共通のヘッダー
    sys_branch = st.session_state.get('sys_branch', '')
    branch_display = ""
    if sys_branch:
        # 「田端新町校:T, 池上校:I」のようになっているデータを「田端新町校 / 池上校」に整形
        clean_names = [b.split(':')[0] for b in sys_branch.split(', ')]
        branch_display = f"【{' / '.join(clean_names)}】"
    
    st.markdown(f"""
    <div style="background-color:#1E90FF;padding:10px;border-radius:10px;margin-bottom:20px;">
        <h2 style="color:white;text-align:center;margin:0;">🌟 管理システムK-AI {branch_display} <span style="font-size:0.5em;background-color:white;color:#1E90FF;padding:2px 8px;border-radius:5px;">{st.session_state['username']} モード</span></h2>
    </div>
    """, unsafe_allow_html=True)

    # サイドバーのメニュー作成
    st.sidebar.title(f"👤 {st.session_state['username']} メニュー")
    
    menu_options = [
        "📢 ホーム",
        "📝 授業・自習記録の入力 (出欠対応)",
        "🏫 教室・学習状況ダッシュボード",
        "👤 生徒個別ポータル",
        "💯 小テスト管理センター",
        "🔍 全生徒の過去ログ検索",
        "🎒 学校課題管理",
    ]

    if st.session_state['role'] in ['admin', 'sub_admin', 'owner', 'am', 'head_teacher']:
        menu_options.extend([
            "📱 LINE用 学習レポート生成"
        ])

    if st.session_state['role'] in ['admin', 'sub_admin', 'owner', 'am']:
        menu_options.extend([
            "📈 講師分析ダッシュボード",
            "⚙️ アカウント・システム設定",
            "💰 財務・請求ダッシュボード"
        ])
    else:
        # 👨‍🏫 一般講師専用
        menu_options.extend([
            "💴 自分の給与確認"
        ])
        
    page = st.sidebar.radio("移動先", menu_options)

    st.sidebar.divider()
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # ==========================================
    # 🎯 画面遷移
    # ==========================================
    if page == "📢 ホーム": render_combined_home_page()
    elif page == "📝 授業・自習記録の入力 (出欠対応)": render_combined_input_page()
    elif page == "👤 生徒個別ポータル": render_student_portal_page()
    elif page == "💯 小テスト管理センター": render_quiz_management_page()
    elif page == "🏫 教室・学習状況ダッシュボード":render_combined_dashboard_page()
    elif page == "🎒 学校課題管理": render_school_homework_page()
    elif page == "📱 LINE用 学習レポート生成": render_line_report_page()
    elif page == "🔍 全生徒の過去ログ検索": render_search_page()
    elif page == "📈 講師分析ダッシュボード": render_analytics_dashboard_page()
    elif page == "💴 自分の給与確認": render_my_salary_page()
    elif page == "💰 財務・請求ダッシュボード": render_finance_integrated_page()
    elif page == "⚙️ アカウント・システム設定": render_account_manager_page()

if __name__ == "__main__":
    main()