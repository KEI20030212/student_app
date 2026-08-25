import streamlit as st
import pandas as pd
import datetime

from utils.g_sheets import load_quiz_records
from utils.api_guard import robust_api_call

# 🌟 二重キャッシュ防止のため、ここには@st.cache_dataを付けずに原本を直接呼び出す
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def render_quiz_tab(student_options):
    with st.spinner("小テストデータベースから読み込み中...🚀"):
        df_quiz_raw = cached_load_quiz_records()
        df_quiz = df_quiz_raw.copy()
    
    if df_quiz.empty or "APIエラー発生" in df_quiz.columns:
        st.info("💡 まだ小テスト記録がないか、通信エラーによりデータを取得できませんでした。")
        return # データがなければストップ
    
    df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
    
    if '名前' in df_quiz.columns:
        if '生徒名' in df_quiz.columns:
            df_quiz = df_quiz.drop(columns=['名前'])
        else:
            df_quiz = df_quiz.rename(columns={'名前': '生徒名'})

    with st.container(border=True):
        st.markdown("**🔍 小テスト記録の検索条件と表示設定**")
        
        cq1, cq2, cq3 = st.columns(3)
        
        min_q_date = df_quiz['日時'].min().date() if not pd.isnull(df_quiz['日時'].min()) else datetime.date.today()
        max_q_date = df_quiz['日時'].max().date() if not pd.isnull(df_quiz['日時'].max()) else datetime.date.today()
        q_date_range = cq1.date_input("📅 日付の範囲", [min_q_date, max_q_date], key="quiz_date_range")
        
        q_students = ["すべて"] + student_options
        selected_q_student = cq2.selectbox("👤 生徒名", q_students, key="quiz_student")
        
        if 'テキスト' in df_quiz.columns:
            valid_texts = [t for t in df_quiz['テキスト'].dropna().unique() if t and str(t).strip() not in ["None", "nan", ""]]
            q_texts = ["すべて"] + sorted(valid_texts)
        else:
            q_texts = ["すべて"]
            
        selected_q_text = cq3.selectbox("📘 テキスト", q_texts, key="quiz_text")

        st.write("")
        quiz_columns_list = ["日時", "生徒名", "テキスト", "単元", "点数", "ミス問題番号", "タイミング"]
        available_q_cols = [col for col in quiz_columns_list if col in df_quiz.columns or col == "日時"]
        default_q_cols = [col for col in ["日時", "生徒名", "テキスト", "単元", "点数"] if col in available_q_cols]

        selected_display_q_cols = st.multiselect(
            "📋 表に表示する項目（クリックでON/OFFを切り替え）",
            options=available_q_cols,
            default=default_q_cols,
            key="quiz_display_cols"
        )

    # 絞り込み処理
    df_q_filtered = df_quiz.copy()
    if len(q_date_range) == 2:
        df_q_filtered = df_q_filtered[(df_q_filtered['日時'].dt.date >= q_date_range[0]) & (df_q_filtered['日時'].dt.date <= q_date_range[1])]
    
    if selected_q_student != "すべて":
        search_q_name = selected_q_student.split(" - ")[1]
        df_q_filtered = df_q_filtered[df_q_filtered['生徒名'] == search_q_name]
        
    if selected_q_text != "すべて":
        df_q_filtered = df_q_filtered[df_q_filtered['テキスト'] == selected_q_text]

    df_q_filtered['日時'] = df_q_filtered['日時'].dt.strftime('%Y/%m/%d')
    df_q_display = df_q_filtered.fillna("")

    if df_q_display.empty:
        st.info("💡 指定された条件の小テスト記録は見つかりませんでした。\n日付の範囲を広げるか、別の生徒・テキストを選択してみてください。")
    else:
        st.success(f"該当記録: **{len(df_q_filtered)} 件**")
        if selected_display_q_cols:
            st.dataframe(df_q_display[selected_display_q_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ 表示項目が何も選択されていません。項目を1つ以上選択してください。")