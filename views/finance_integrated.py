import streamlit as st

# 各画面の描画関数を読み込む
from views.tuition_dashboard import render_tuition_dashboard_page
from views.salary_dashboard import render_salary_dashboard_page
from views.my_salary import render_my_salary_page
from views.profit_loss_dashboard import render_profit_loss_dashboard_page

def render_finance_integrated_page():
    # --- 1. メインエリア最上部に「擬似タブ」メニューを作成 ---
    # horizontal=True で横並びにし、divider=True で境界線を引きます
    menu_selection = st.radio(
        "財務メニュー選択",
        [
            "💴 月謝管理", 
            "💰 給与・交通費", 
            "👩‍🏫 講師マイページ", 
            "📈 損益ダッシュボード"
        ],
        horizontal=True,
        label_visibility="collapsed" # ラベルを隠してボタンだけに
    )
    
    # メニューとコンテンツの間に少し隙間を作る
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 2. 選択された画面「だけ」を実行（他の画面のAPIは呼ばれない） ---
    if menu_selection == "💴 月謝管理":
        render_tuition_dashboard_page()
        
    elif menu_selection == "💰 給与・交通費":
        render_salary_dashboard_page()
        
    elif menu_selection == "👩‍🏫 講師マイページ":
        render_my_salary_page()
        
    elif menu_selection == "📈 損益ダッシュボード":
        render_profit_loss_dashboard_page()
# もしこのファイルが直接実行された場合の処理（必要に応じて）
if __name__ == "__main__":
    render_finance_integrated_page()