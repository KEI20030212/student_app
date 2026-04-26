import streamlit as st

# 完成している2つのファイルを部品として読み込む
from views.my_salary import render_my_salary_page
from views.salary_dashboard import render_salary_dashboard_page

def render_salary_combined_page():
    # 🌟 ログイン中のユーザー権限を取得
    # ※ "role" の部分は、実際のログイン機能で使っている変数名に合わせてください
    role = st.session_state.get("role", "teacher") # 万が一取得できなかった時のデフォルトを "teacher" にしておく

    # 👨‍💼 管理者陣（オーナー、教室長、エリアマネージャー）の場合（タブで両方表示）
    if role in ["owner", "admin", "am"]:
        tab1, tab2 = st.tabs(["💴 自分の給与確認", "💰 給与ダッシュボード（管理者用）"])
        
        with tab1:
            render_my_salary_page()
            
        with tab2:
            render_salary_dashboard_page()
            
    # 👩‍🏫 講師陣（主任講師、講師）の場合（自分の給与確認のみ表示）
    elif role in ["head_teacher", "teacher"]:
        render_my_salary_page()
        
    # それ以外（予期せぬエラー防止）
    else:
        st.error("権限が正しく設定されていないため、このページを表示できません。")