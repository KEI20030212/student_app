import streamlit as st
import time
import pandas as pd

# 🌟 変更: get_all_student_names を削除し、マスター取得関数とAPIガードをインポート
from utils.g_sheets import get_student_master, get_student_info
from utils.api_guard import robust_api_call

from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
from views.conference_report import render_conference_report

def render_student_portal_page():
    col_title, col_toggle = st.columns([3, 1])
    
    with col_title:
        st.header("🏫 生徒個別ポータル")
        
    with col_toggle:
        st.markdown("<br>", unsafe_allow_html=True) # スイッチの高さをタイトルと合わせるための微調整
        is_conference_mode = st.toggle("👨‍👩‍👦 面談モード", value=False)
        
    if is_conference_mode:
        st.caption("✅ 面談モードON（読取専用）※保護者と一緒に画面を見るためのモードです。")

    # ==========================================
    # 🌟 変更: get_student_master を使って「ID - 名前」のリストを爆速で生成
    # ==========================================
    student_options = []
    with st.spinner("生徒データを読み込み中..."):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
            # "S001 - 山田太郎" のリストを作る
            student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
            
    if not student_options: 
        st.warning("まだ生徒が登録されていないか、データの読み込みに失敗しました。")
        return

    # 🌟 全機能共通の生徒選択バー（ID付きのリストを渡す）
    selected_student = st.selectbox("👤 対象の生徒を選択してください", student_options, index=None, placeholder="--選択--")

    if is_conference_mode:
        st.sidebar.success("✅ 面談モードON（読取専用）")
        st.sidebar.caption("※保護者と一緒に画面を見るためのモードです。")
    else:
        st.sidebar.info("✏️ 通常モード（入力・編集）")

    # 🌟 生徒が選ばれていない時の「機能紹介画面」
    if selected_student is None:
        st.info("👆 上のメニューから生徒を選択すると、以下の個別メニューが利用できます！")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("### 👤 生徒詳細・成績入力")
                st.write("生徒の基本データや、テスト結果を管理します。")
                st.markdown("""
                - **🩺 カルテ**: 能力・やる気マトリクスの確認
                - **✍️ 成績入力**: 定期テスト・内申点・模試の入力
                - **📈 成績推移**: 過去の点数グラフの確認
                """)
        with c2:
            with st.container(border=True):
                st.markdown("### 📊 個別分析・履歴・振替")
                st.write("日々の授業履歴や、未消化の振替授業を管理します。")
                st.markdown("""
                - **⚠️ 振替管理**: 未消化の授業コマ数を自動カウント
                - **📊 学習グラフ**: ページ数や単元ごとの点数を可視化
                - **📚 履歴編集**: 過去の授業記録をスプレッドシートに直接上書き修正
                """)
        return


    # ==========================================
    # 🌟 モードの分岐
    # ==========================================
    if is_conference_mode:
        with st.spinner("面談用データを準備中..."):
            # ここに渡る selected_student は "S001 - 山田太郎"
            info = get_student_info(selected_student) 
            
        render_conference_report(selected_student, info)
        
    else:
        app_mode = st.radio(
            "📂 表示するメニューを選んでください", 
            ["👤 生徒詳細・成績入力", "📊 個別分析・履歴・振替管理"], 
            horizontal=True
        )
        
        st.divider()
        
        if app_mode == "👤 生徒詳細・成績入力":
            render_student_details_page(selected_student)
        else:
            render_analysis_page(selected_student)