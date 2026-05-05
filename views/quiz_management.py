import streamlit as st
from views.quiz_maker import render_quiz_maker_page
from views.quiz_dashboard import render_quiz_list_page
from views.word_quiz_maker import render_word_quiz_maker_page 

def render_quiz_management_page():
    st.header("💯 小テスト管理センター")
    st.write("小テストの作成・印刷から、生徒ごとの結果記録・進捗確認までここで行えます。")
    
    tab1, tab2, tab3 = st.tabs([
        "🖨️ 小テスト作成・印刷", 
        "🔤 単語テスト作成", 
        "📝 進捗＆習熟度マップ"
    ])
    
    with tab1:
        render_quiz_maker_page()
        
    with tab2:
        render_word_quiz_maker_page()

    with tab3:
        render_quiz_list_page()