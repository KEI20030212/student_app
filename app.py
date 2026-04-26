import streamlit as st
from PIL import Image
# ==========================================
# 📦 1. 画面部隊（views）のインポート
# ==========================================
from views.home import render_home_page
from views.attendance_seat import render_attendance_seat_page
from views.multi_input import render_multi_input_page
#from views.quiz_maker import render_quiz_maker_page
from views.student_details import render_student_details_page
#from views.dashboard import render_dashboard_page
#from views.quiz_dashboard import render_quiz_list_page
#from views.self_study_dashboard import render_self_study_dashboard
# ※まだ作っていない画面はエラー防止のためコメントアウト(#)しています
from views.analysis import render_analysis_page
# from views.quiz_list import render_quiz_list_page
from views.search_page import render_search_page
#from views.salary_dashboard import render_salary_dashboard_page
from views.analytics_dashboard import render_analytics_dashboard_page
#from views.tuition_dashboard import render_tuition_dashboard_page
from views.my_salary import render_my_salary_page
from views.account_manager import render_account_manager_page
from views.message_sender import render_message_sender_page
#from views.salary_combined import render_salary_combined_page
from views.dashboard_combined import render_combined_dashboard_page
from views.student_portal import render_student_portal_page
from views.quiz_management import render_quiz_management_page
from views.line_report import render_line_report_page
from views.school_homework import render_school_homework_page
from views.finance_integrated import render_finance_integrated_page
# ==========================================
# 🛠️ 2. 裏方部隊（utils）のインポート
# ==========================================
from utils.calc_logic import calculate_hw_rate, calculate_quiz_points, calculate_motivation_rank
from utils.g_sheets import load_textbook_master, get_textbook_master, add_new_textbook, get_last_homework_info
from utils.g_sheets import get_all_accounts


# ページの基本設定
img = Image.open("icon.jpg")
st.set_page_config(page_title="学習塾管理システム", page_icon=img, layout="wide")

# 🔑 パスワード設定
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
TEACHER_USER = "teacher"
TEACHER_PASS = "teacher123"

# --------------------------------------------------
# 🔒 ログイン画面
# --------------------------------------------------
def login_screen():
    st.markdown("<h1 style='text-align: center; color: #1E90FF;'>🌟 Dr.関塾(田端新町校) 統合管理システム</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("👤 ユーザーID")
            password = st.text_input("🔑 パスワード", type="password")
            submit = st.form_submit_button("ログイン 🚀", use_container_width=True)
            if submit:
                if username == ADMIN_USER and password == ADMIN_PASS:
                    st.session_state.update({'logged_in': True, 'role': 'admin', 'username': '教室長', 'user_id': 'admin'})
                    st.rerun()
                elif username == TEACHER_USER and password == TEACHER_PASS:
                    st.session_state.update({'logged_in': True, 'role': 'teacher', 'username': '先生', 'user_id': 'teacher'})
                    st.rerun()
                else:
                    accounts = get_all_accounts()

                    # IDが存在し、かつパスワード（数字のみの場合に備えてstr変換）が一致するかチェック
                    if username in accounts and str(accounts[username].get('パスワード')) == str(password):
                        st.session_state.update({
                            'logged_in': True, 
                            'role': accounts[username].get('権限', 'teacher'),
                            'username': accounts[username].get('講師名', '先生'),
                            'user_id': username
                        })
                        st.rerun()
                    else:
                        st.error("⚠️ IDまたはパスワードが間違っています。")

# --------------------------------------------------
# 🚀 メイン画面＆ルーティング（司令塔）
# --------------------------------------------------
def main():
    # ログインしていない場合はログイン画面を表示して終了
    if not st.session_state.get('logged_in', False):
        login_screen()
        return

    # 全画面共通のヘッダー
    st.markdown(f"""
    <div style="background-color:#1E90FF;padding:10px;border-radius:10px;margin-bottom:20px;">
        <h2 style="color:white;text-align:center;margin:0;">🌟 Dr.関塾(田端新町校) 統合管理システム <span style="font-size:0.5em;background-color:white;color:#1E90FF;padding:2px 8px;border-radius:5px;">{st.session_state['username']} モード</span></h2>
    </div>
    """, unsafe_allow_html=True)

    # サイドバーのメニュー作成
    st.sidebar.title(f"👤 {st.session_state['username']} メニュー")
    
    menu_options = [
        "📢 ホーム・連絡・出席掲示板",
        "📝 授業・自習記録の入力 (出欠対応)", 
        #"🖨️ 小テスト作成・印刷",
        "🏫 教室・学習状況ダッシュボード",
        "👤 生徒個別ポータル",
        "💯 小テスト管理センター",
        "🎒 学校課題管理",
        #"👤 生徒詳細 ＆ テスト成績",
        #"🌐 クラス全体ダッシュボード",
        #"📊 個別分析・履歴・振替管理",
        #"📝 小テスト進捗マップ",
        #"📊 自習時間ランキング",
        #"💴 自分の給与確認",
        #"💸 給与メニュー",
        "💌 メッセージ送信"
    ]

    if st.session_state['role'] in ['admin', 'owner', 'head_teacher']:
        menu_options.extend([
            "📱 LINE用 学習レポート生成"
        ])

    if st.session_state['role'] in ['admin', 'owner']:
        menu_options.extend([
            #"✅ 本日の出欠・座席表",#home.pyに統合
            "🔍 全生徒の過去ログ検索",
            #"💰 給与・交通費ダッシュボード",
            "📈 講師分析ダッシュボード",
            "⚙️ アカウント・システム設定",
            #"💴 月謝（請求額）管理ダッシュボード"
            "💰 財務・請求ダッシュボード"
        ])
    else:
        # 👨‍🏫 一般講師専用（自分に関することだけ）
        menu_options.extend([
            "💴 自分の給与確認"             # ← my_salary.py を表示
        ])
        
    page = st.sidebar.radio("移動先", menu_options)

    # ログアウトボタン
    st.sidebar.divider()
    if st.sidebar.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # 必要なマスターデータをロード
    textbook_master = load_textbook_master()

    # ==========================================
    # 🎯 選ばれたメニューに応じて、該当する画面関数を呼び出すだけ！
    # ==========================================
    if page == "📢 ホーム・連絡・出席掲示板": render_home_page()
    #elif page == "✅ 本日の出欠・座席表": render_attendance_seat_page()　　#home.pyに統合
    elif page == "📝 授業・自習記録の入力 (出欠対応)": render_multi_input_page(textbook_master)
    #elif page == "🖨️ 小テスト作成・印刷": render_quiz_maker_page()
    elif page == "👤 生徒個別ポータル": render_student_portal_page()
    elif page == "💯 小テスト管理センター": render_quiz_management_page()
    #elif page == "👤 生徒詳細 ＆ テスト成績": render_student_details_page()
    elif page == "🏫 教室・学習状況ダッシュボード":render_combined_dashboard_page()
    elif page == "🎒 学校課題管理": render_school_homework_page()
    #elif page == "🌐 クラス全体ダッシュボード": render_dashboard_page()
    #elif page == "📝 小テスト進捗マップ":render_quiz_list_page()
    #elif page == "📊 自習時間ランキング":render_self_study_dashboard()
    #elif page == "📊 個別分析・履歴・振替管理": render_analysis_page(),
    # elif page == "💯 小テスト成績・アラート": render_quiz_list_page(textbook_master)
    elif page == "📱 LINE用 学習レポート生成": render_line_report_page()
    elif page == "🔍 全生徒の過去ログ検索": render_search_page()
    #elif page == "💰 給与・交通費ダッシュボード": render_salary_dashboard_page(),
    elif page == "📈 講師分析ダッシュボード": render_analytics_dashboard_page()
    #elif page == "💴 月謝（請求額）管理ダッシュボード": render_tuition_dashboard_page()
    elif page == "💴 自分の給与確認": render_my_salary_page()
    elif page == "💰 財務・請求ダッシュボード": render_finance_integrated_page()
    #elif page == "💸 給与メニュー": render_salary_combined_page()
    elif page == "💌 メッセージ送信": render_message_sender_page()
    elif page == "⚙️ アカウント・システム設定": render_account_manager_page()

if __name__ == "__main__":
    main()