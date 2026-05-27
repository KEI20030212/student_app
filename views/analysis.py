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
            
            # 🌟 文字列から「テキスト名」と「進捗ページ数」を自動抽出する高度な関数
            import re
            def parse_page_data(row):
                val = row.get('終了ページ')
                if pd.isna(val): return None, None
                s = str(val).strip()
                if not s: return None, None
                
                # 初期値のセット（スプレッドシートの「テキスト」列を仮セット）
                text_name = row.get('テキスト', '')
                if pd.isna(text_name): text_name = ''
                page_str = s
                
                # 1️⃣ 「終了ページ」のセル内にコロン(:)があれば、テキスト名とページ部分に切り分ける
                if ':' in s:
                    parts = s.split(':', 1)
                    text_name = parts[0].strip()
                    page_str = parts[1].strip()
                
                # 2️⃣ ページ部分から「〜」や「-」の後ろ側（終了ページ数）を切り出す
                if '〜' in page_str:
                    target = page_str.split('〜')[-1]
                elif '-' in page_str:
                    target = page_str.split('-')[-1]
                else:
                    target = page_str
                
                # 3️⃣ 切り出した部分から数字を抽出
                nums = re.findall(r'\d+', target)
                page_num = int(nums[-1]) if nums else None
                
                # 保険：もし上記で取れなければ、ページ文字列全体から一番最後の数字を探す
                if page_num is None:
                    all_nums = re.findall(r'\d+', page_str)
                    if all_nums:
                        page_num = int(all_nums[-1])
                
                # テキスト名がどうしても空なら「科目」や「その他」にする
                if not str(text_name).strip():
                    text_name = row.get('科目', 'その他')
                    if pd.isna(text_name) or not str(text_name).strip():
                        text_name = 'その他'
                        
                return text_name, page_num

            # 🌟 各行に上の関数を適用して「グラフ用テキスト名」と「数値のページ数」を新しく生成
            res = df_history.apply(parse_page_data, axis=1, result_type='expand')
            df_history['グラフ用テキスト'] = res[0]
            df_history['グラフ用ページ'] = res[1]

            # 日時とページ数値が両方揃っている有効なデータだけに絞り込んでソート
            df_chart = df_history.dropna(subset=['日時', 'グラフ用ページ']).sort_values('日時')
            
            if not df_chart.empty:
                # 抽出したテキスト名ごとにグループを回す
                text_names = df_chart['グラフ用テキスト'].unique()
                has_graph = False
                
                for t_name in text_names:
                    if str(t_name).strip() == "": continue
                    
                    df_sub = df_chart[df_chart['グラフ用テキスト'] == t_name]
                    if not df_sub.empty:
                        st.markdown(f"##### 📘 {t_name}")
                        st.line_chart(data=df_sub, x="日時", y="グラフ用ページ")
                        has_graph = True
                        
                if not has_graph:
                    st.info("表示できる有効なデータがありません。")
            else:
                st.info("グラフに表示できる有効なページデータがありません。（終了ページの文字からページ数値を読み取れませんでした）")

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