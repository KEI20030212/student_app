import streamlit as st
import pandas as pd
import time # 🌟 APIエラー対策
import gspread # 🌟 APIエラー対策
from utils.g_sheets import (
    load_all_data,
    load_raw_data,          
    overwrite_spreadsheet   
)

# 🌟 変更: 親から name を受け取るようにしました！
def render_analysis_page(name):
    # 🌟 APIエラー対策付きの読み込み
    df_history = pd.DataFrame()
    with st.spinner("📊 データを取得中..."):
        max_retries = 5
        for attempt in range(max_retries):
        #for attempt in range(3):
            try:
                df_history = load_all_data(name)
                break
            except Exception:
                if attempt < max_retries - 1: 
                    time.sleep(2 ** attempt)
                #if attempt < 2: time.sleep(2)

    if not df_history.empty and '出欠' in df_history.columns:
        absent_count = len(df_history[df_history['出欠'] == '欠席（後日振替あり）'])
        makeup_count = len(df_history[df_history['出欠'] == '出席（振替授業を消化）'])
        balance = absent_count - makeup_count
        if balance > 0:
            st.error(f"⚠️ **未消化の振替授業が【 {balance} コマ 】残っています！** (欠席: {absent_count}回 / 振替消化: {makeup_count}回)")
        else:
            st.success("✅ 現在、未消化の振替授業はありません。")

    tab_report, tab_history = st.tabs(["📊 グラフ＆レポート", "📚 過去の履歴 (直接編集)"])

    with tab_report:
        if df_history.empty: 
            st.info("データがありません。")
        else:
            df_history['日時'] = pd.to_datetime(df_history['日時'], format='mixed')
            df_history = df_history.sort_values('日時')
            col_g1, col_g2 = st.columns(2)
            with col_g1: 
                st.markdown("**📖 ページ進捗グラフ**")
                st.line_chart(data=df_history, x="日時", y="ページ数")
            with col_g2:
                st.markdown("**💯 単元別小テスト点数**")
                df_history['数値点数'] = pd.to_numeric(df_history['点数'], errors='coerce')
                df_quiz = df_history.dropna(subset=['数値点数']).copy()
                if not df_quiz.empty: st.bar_chart(data=df_quiz, x="単元", y="数値点数")

    with tab_history:
        # 🌟 APIエラー対策付きの生データ読み込み
        raw_df = pd.DataFrame()
        for attempt in range(max_retries):
        #for attempt in range(3):
            try:
                raw_df = load_raw_data(name)
                break
            except Exception:
                if attempt < max_retries - 1: 
                    time.sleep(2 ** attempt)

        if not raw_df.empty:
            st.info("💡 以下の表のセルを直接クリックして書き換え、下の「上書き保存」ボタンを押してください。")
            edited_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 上書き保存", type="primary"): 
                with st.spinner("☁️ データを上書き保存中...（混雑時は自動で再試行します）"):
                    # 🌟 APIエラー対策付きの保存
                    for attempt in range(max_retries):
                    #for attempt in range(3):
                        try:
                            overwrite_spreadsheet(name, edited_df)
                            st.success("✨ データを上書き保存しました！")
                            break
                        except Exception:
                            if attempt < max_retries - 1: 
                                time.sleep(2 ** attempt)
                            #if attempt < 2: time.sleep(2)
                            else: st.error("保存に失敗しました。時間をおいてやり直してください。")