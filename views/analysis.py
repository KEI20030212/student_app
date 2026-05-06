import streamlit as st
import pandas as pd
import time 

from utils.g_sheets import (
    get_all_logs, # 🌟 生徒ごとの関数から、統合シート読み込み関数に変更！
    load_quiz_records  
)

# 🌟 APIガードをインポート
from utils.api_guard import robust_api_call

# 🌟 修正: 引数名を selected_student に変更
def render_analysis_page(selected_student=None):
    
    # 🌟 修正: 受け取った引数がID付きかどうかを判定して安全に分割
    if selected_student and " - " in selected_student: 
        student_id = selected_student.split(" - ")[0]
        name = selected_student.split(" - ")[1]
    else:
        # 万が一「山田太郎」のようにIDがついていない古いデータが来た時の保険
        name = selected_student
        student_id = "未設定"
        
    with st.spinner("📊 データを取得中..."):
        # 1. 🌟 「授業ログ統合」シートの全データを取得
        df_all_logs = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
        
        # 2. 小テスト記録シートの全データ取得
        df_all_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

    # 🌟 全データの中から、現在の生徒のデータだけに絞り込み（フィルタリング）
    df_history = pd.DataFrame()
    if not df_all_logs.empty and '名前' in df_all_logs.columns:
        df_history = df_all_logs[df_all_logs['名前'] == name].copy()

    # --- 振替授業の計算 (df_historyを使用) ---
    if not df_history.empty and '出欠' in df_history.columns:
        absent_count = len(df_history[df_history['出欠'] == '欠席（後日振替あり）'])
        makeup_count = len(df_history[df_history['出欠'] == '出席（振替授業を消化）'])
        balance = absent_count - makeup_count
        if balance > 0:
            st.error(f"⚠️ **未消化の振替授業が【 {balance} コマ 】残っています！** (欠席: {absent_count}回 / 振替消化: {makeup_count}回)")
        else:
            st.success("✅ 現在、未消化の振替授業はありません。")

    tab_report, tab_history = st.tabs(["📊 グラフ＆レポート", "📚 過去の履歴"])

    with tab_report:
        # --- ページ進捗グラフ (df_historyを使用) ---
        if df_history.empty: 
            st.info("進捗データがありません。")
        else:
            st.markdown("**📖 ページ進捗グラフ**")
            # 日付データを正しくソートするために変換
            df_history['日時'] = pd.to_datetime(df_history['日時'], format='mixed', errors='coerce')
            df_history = df_history.dropna(subset=['日時']).sort_values('日時')
            
            if 'ページ数' in df_history.columns:
                st.line_chart(data=df_history, x="日時", y="ページ数")
            elif '終了ページ' in df_history.columns: # 列名が「終了ページ」の可能性があるための対応
                df_history['終了ページ'] = pd.to_numeric(df_history['終了ページ'], errors='coerce')
                st.line_chart(data=df_history.dropna(subset=['終了ページ']), x="日時", y="終了ページ")

        st.divider()

        # --- 🌟 小テスト点数グラフ (df_all_quizzesを使用) ---
        st.markdown("**💯 テキスト別・単元別小テスト点数**")
        
        if df_all_quizzes.empty:
            st.info("小テストの記録が見つかりません。")
        else:
            # 「名前」列で現在の生徒のみに絞り込み
            df_student_quiz = df_all_quizzes[df_all_quizzes['名前'] == name].copy()
            
            if df_student_quiz.empty:
                st.info(f"{name}さんの小テスト記録はまだありません。")
            else:
                # 「点数」列を数値に変換（エラーはNaNにする）
                df_student_quiz['数値点数'] = pd.to_numeric(df_student_quiz['点数'], errors='coerce')
                # グラフ表示用に、点数が入っていない行を削除
                df_quiz_chart = df_student_quiz.dropna(subset=['数値点数'])
                
                if not df_quiz_chart.empty:
                    # スプレッドシートの列名に合わせてテストごとにグラフを分ける
                    target_column = "テキスト"  
                    
                    if target_column in df_quiz_chart.columns:
                        text_names = df_quiz_chart[target_column].unique()
                        
                        for t_name in text_names:
                            st.markdown(f"##### 📗 {t_name}")
                            df_sub = df_quiz_chart[df_quiz_chart[target_column] == t_name]
                            
                            chart_x = "単元" if "単元" in df_sub.columns else "日時"
                            st.bar_chart(data=df_sub, x=chart_x, y="数値点数")
                    else:
                        chart_x = "単元" if "単元" in df_quiz_chart.columns else "日時"
                        st.bar_chart(data=df_quiz_chart, x=chart_x, y="数値点数")
                else:
                    st.info("有効な点数データがありません。")

    with tab_history:
        st.markdown("### 📚 過去の授業ログ")
        
        if not df_history.empty:
            # 🚨 統合シート破壊を防ぐための安全ロック（読み取り専用表示）
            st.info("💡 現在、データは全員分が「授業ログ統合」シートに集約されています。他の生徒のデータ上書きを防ぐため、ここからの直接編集はロックされています。修正が必要な場合はスプレッドシートを直接修正してください。")
            
            # 日時で降順（新しい順）に並び替えて見やすくする
            df_display = df_history.sort_values(by="日時", ascending=False)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info(f"「授業ログ統合」シートに {name} さんの履歴は見つかりませんでした。")