import streamlit as st
import time
from utils.g_sheets import get_all_student_names
from utils.g_sheets import get_student_info

# 完成している2つのファイルを部品として読み込む
from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
# 🌟 修正: 名前を正しく「render_conference_report」にしました
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

    # 🌟 変更: 生徒一覧の取得にも Exponential Backoff を適用
    student_names = []
    max_retries = 5
    with st.spinner("生徒データを読み込み中..."):
        for attempt in range(max_retries):
            try:
                student_names = get_all_student_names()
                # 取得できたらループを抜ける（空っぽのリストが返ってきた場合もエラーではないので抜ける）
                if student_names is not None: 
                    break
            except Exception:
                pass # エラーが起きても下に進んで待機する
            
            # 取得に失敗したら、待機時間を倍にして再チャレンジ (1秒, 2秒, 4秒, 8秒...)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
    if not student_names: 
        st.warning("まだ生徒が登録されていません。")
        return

    # 🌟 全機能共通の生徒選択バー
    selected_student = st.selectbox("👤 対象の生徒を選択してください", ["-- 選択 --"] + student_names)

    # ==========================================
    # 🌟 NEW! サイドバーに面談モードのスイッチを追加
    # ==========================================
    #st.sidebar.divider()
    #is_conference_mode = st.sidebar.toggle("👨‍👩‍👦 面談モード", value=False)
    
    if is_conference_mode:
        st.sidebar.success("✅ 面談モードON（読取専用）")
        st.sidebar.caption("※保護者と一緒に画面を見るためのモードです。")
    else:
        st.sidebar.info("✏️ 通常モード（入力・編集）")

    # ==========================================

    # 🌟 生徒が選ばれていない時の「機能紹介画面」！
    if selected_student == "-- 選択 --":
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
    # 🌟 ここで「面談モード」と「通常モード」を分岐させます！
    # ==========================================
    if is_conference_mode:
        # 面談モードがONのとき：面談レポートだけを全画面に表示する
        with st.spinner("面談用データを準備中..."):
            info = get_student_info(selected_student) # 面談画面で使うため情報を取得
            
        render_conference_report(selected_student, info)
        
    else:
        # 面談モードがOFF（通常）のとき：いつものメニューを表示する
        app_mode = st.radio(
            "📂 表示するメニューを選んでください", 
            ["👤 生徒詳細・成績入力", "📊 個別分析・履歴・振替管理"], 
            horizontal=True
        )
        
        st.divider()
        
        # 選ばれた機能に応じて、生徒名を渡しながら画面を呼び出す
        if app_mode == "👤 生徒詳細・成績入力":
            render_student_details_page(selected_student)
        else:
            render_analysis_page(selected_student)