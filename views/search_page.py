import streamlit as st
import pandas as pd
import datetime  # 👈 今日の日付（today）を取得するための必須ツール！
from utils.g_sheets import (
    get_all_student_names,
    load_entire_log_data,  # 👈 全生徒のデータを一括で読み込む関数！
    delete_specific_log    # 👈 間違えた記録を消し去る関数！
)

def render_search_page():
    st.header("🔍 全生徒の過去ログ検索 ＆ 修正")
    
    # ==========================================
    # 🌟 None対策 1: 生徒名リストから空っぽのデータ（None）を追い出す！
    # ==========================================
    raw_student_names = get_all_student_names()
    # もしNoneや空白が含まれていたら除外し、キレイなリストだけを残します
    student_names = [name for name in raw_student_names if name and str(name).strip() not in ["None", "nan", ""]] if raw_student_names else []

    if st.session_state.get('role') == 'admin':
        with st.expander("🗑️ 間違えて入力した授業記録を削除する (教室長のみ)"):
            st.warning("※スプレッドシートから直接データを消去します。元には戻せません。")
            with st.form("delete_log_form"):
                d_col1, d_col2, d_col3 = st.columns(3)
                # ここもキレイにした student_names を使います
                del_name = d_col1.selectbox("削除する生徒", student_names)
                del_date = d_col2.date_input("間違えた授業日", datetime.date.today())
                del_subject = d_col3.selectbox("間違えた科目", ["英語", "数学", "国語", "理科", "社会"])
                
                if st.form_submit_button("🚨 この記録を削除する", type="primary"):
                    date_str = del_date.strftime("%Y/%m/%d")
                    success = delete_specific_log(del_name, date_str, del_subject)
                    if success:
                        st.success(f"✅ {date_str} の {del_name} さん ({del_subject}) の記録を削除しました！下の表にも反映されています。")
                    else:
                        st.error("⚠️ 該当する記録が見つかりませんでした。日付や科目を確認してください。")
    
    st.divider()

    if not student_names: 
        st.warning("生徒が登録されていません。")
        return

    with st.spinner("データベースから一括読み込み中..."):
        df_all = load_entire_log_data()
    
    if df_all.empty: 
        st.info("まだ授業記録がありません。")
        return
        
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        min_date = df_all['日時'].min().date() if not pd.isnull(df_all['日時'].min()) else datetime.date.today()
        max_date = df_all['日時'].max().date() if not pd.isnull(df_all['日時'].max()) else datetime.date.today()
        date_range = c1.date_input("📅 日付の範囲", [min_date, max_date])
        
        # ==========================================
        # 🌟 None対策 2: 講師名リストからもNoneを追い出す！
        # ==========================================
        if '担当講師' in df_all.columns:
            # dropna() で NaN を消しつつ、文字の "None" も除外します
            valid_teachers = [t for t in df_all['担当講師'].dropna().unique() if t and str(t).strip() not in ["None", "nan", ""]]
            teachers = ["すべて"] + valid_teachers
        else:
            teachers = ["すべて"]
            
        selected_teacher = c2.selectbox("👨‍🏫 担当講師", teachers)
        students = ["すべて"] + student_names
        selected_student = c3.selectbox("👤 生徒名", students)

    df_filtered = df_all.copy()
    if len(date_range) == 2: 
        df_filtered = df_filtered[(df_filtered['日時'].dt.date >= date_range[0]) & (df_filtered['日時'].dt.date <= date_range[1])]
    if selected_teacher != "すべて": 
        df_filtered = df_filtered[df_filtered['担当講師'] == selected_teacher]
    if selected_student != "すべて": 
        df_filtered = df_filtered[df_filtered['生徒名'] == selected_student]

    st.success(f"該当記録: **{len(df_filtered)} 件**")
    
    # 日付をキレイな文字列に変換
    df_filtered['日時'] = df_filtered['日時'].dt.strftime('%Y/%m/%d')
    
    # ==========================================
    # 🌟 None対策 3: 最後に表全体に魔法をかける！
    # ==========================================
    df_display = df_filtered.drop(columns=['ページ数'], errors='ignore')
    # 表の中にある「None」や「NaN」をすべて空っぽの文字（""）に変換して見た目をスッキリさせます
    df_display = df_display.fillna("") 
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)