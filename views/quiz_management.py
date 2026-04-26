import streamlit as st

# 完成している2つのファイルを部品として読み込む
# ※ フォルダ名が「views」の場合の例です。ご自身の環境に合わせて適宜変更してください。
from views.quiz_maker import render_quiz_maker_page
from views.quiz_dashboard import render_quiz_list_page

def render_quiz_management_page():
    st.header("💯 小テスト管理センター")
    st.write("小テストの作成・印刷から、生徒ごとの結果記録・進捗確認までここで行えます。")
    
    # タブを作成
    tab1, tab2 = st.tabs(["🖨️ 小テスト作成・印刷", "📝 進捗＆習熟度マップ"])
    
    with tab1:
        # 小テスト作成・印刷ページを呼び出し
        render_quiz_maker_page()
        
    with tab2:
        # 小テスト進捗＆習熟度マップページを呼び出し
        render_quiz_list_page()