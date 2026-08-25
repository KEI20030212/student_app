import streamlit as st
import pandas as pd
import datetime

from utils.g_sheets import get_all_logs
from utils.api_guard import robust_api_call

def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

def render_lesson_tab(student_options):
    with st.spinner("授業データベースから読み込み中...🚀"):
        df_all = cached_get_all_logs()
    
    if df_all.empty or "APIエラー発生" in df_all.columns: 
        st.info("まだ授業記録がないか、通信エラーによりデータを取得できませんでした。")
        return # データがなければここで処理をストップ
    
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    
    if '名前' in df_all.columns:
        if '生徒名' in df_all.columns:
            df_all = df_all.drop(columns=['名前'])
        else:
            df_all = df_all.rename(columns={'名前': '生徒名'})
    
    with st.container(border=True):
        st.markdown("**🔍 授業記録の検索条件と表示設定**")
        
        c1, c2, c3, c4 = st.columns(4)
        
        min_date = df_all['日時'].min().date() if not pd.isnull(df_all['日時'].min()) else datetime.date.today()
        max_date = df_all['日時'].max().date() if not pd.isnull(df_all['日時'].max()) else datetime.date.today()
        date_range = c1.date_input("📅 日付の範囲", [min_date, max_date], key="lesson_date_range")
        
        if '科目' in df_all.columns:
            valid_subjects = [s for s in df_all['科目'].dropna().unique() if s and str(s).strip() not in ["None", "nan", ""]]
            subjects = ["すべて"] + valid_subjects
        else:
            subjects = ["すべて"]
            
        selected_subject = c2.selectbox("📚 科目", subjects, key="lesson_subject")
        
        students = ["すべて"] + student_options
        selected_student_option = c3.selectbox("👤 生徒名", students, key="lesson_student")

        if '担当講師' in df_all.columns:
            valid_teachers = [t for t in df_all['担当講師'].dropna().unique() if t and str(t).strip() not in ["None", "nan", ""]]
            teachers = ["すべて"] + sorted(valid_teachers)
        else:
            teachers = ["すべて"]
        selected_teacher = c4.selectbox("👨‍🏫 担当講師", teachers, key="lesson_teacher")

        st.write("")
        all_columns_list = [
            "日時", "生徒ID", "生徒名", "科目", "テキスト", "終了ページ", 
            "担当講師", "授業形態", "出欠", "授業コマ", "アドバイス", 
            "保護者への連絡", "次回への引継ぎ", "出した宿題P", "やった宿題P", 
            "やる気ランク", "未達成の理由", "本日の修正策", "次回の宿題テキスト", 
            "次回の宿題ページ数", "遅刻時間", "集中力", "ミスへの反応", "次回の持ち物"
        ]
        
        available_cols = [col for col in all_columns_list if col in df_all.columns or col == "日時"]
        default_cols = [col for col in ["日時", "生徒名", "科目", "終了ページ"] if col in available_cols]
        
        selected_display_cols = st.multiselect(
            "📋 表に表示する項目（クリックでON/OFFを切り替え）",
            options=available_cols,
            default=default_cols,
            key="lesson_display_cols"
        )

    # 絞り込み処理
    df_filtered = df_all.copy()
    if len(date_range) == 2: 
        df_filtered = df_filtered[(df_filtered['日時'].dt.date >= date_range[0]) & (df_filtered['日時'].dt.date <= date_range[1])]
    
    if selected_subject != "すべて": 
        df_filtered = df_filtered[df_filtered['科目'] == selected_subject]
    
    if selected_student_option != "すべて":
        search_id = selected_student_option.split(" - ")[0]
        search_name = selected_student_option.split(" - ")[1]
        if '生徒ID' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['生徒ID'].astype(str) == search_id]
        else:
            df_filtered = df_filtered[df_filtered['生徒名'] == search_name]
    
    if selected_teacher != "すべて":
        df_filtered = df_filtered[df_filtered['担当講師'] == selected_teacher]

    df_filtered['日時'] = df_filtered['日時'].dt.strftime('%Y/%m/%d')
    df_display = df_filtered.drop(columns=['ページ数'], errors='ignore')
    df_display = df_display.fillna("") 

    if df_display.empty:
        st.info("💡 指定された条件の授業記録は見つかりませんでした。\n日付の範囲を広げるか、他の生徒・科目・講師を選択してみてください。")
    else:
        st.success(f"該当記録: **{len(df_filtered)} 件**")
        if selected_display_cols:
            st.dataframe(df_display[selected_display_cols], use_container_width=True, hide_index=True)
            
            st.write("")
            
            @st.dialog("💬 抽出された記録のコメント詳細")
            def show_comment_details(df_subset):
                st.write(f"検索結果の **{len(df_subset)}件** のコメントを表示します。")
                st.divider()
                comment_cols = [c for c in ["アドバイス", "保護者への連絡", "次回への引継ぎ"] if c in df_subset.columns]
                if not comment_cols:
                    st.warning("詳細を表示できるコメント項目が存在しません。")
                    return
                for idx, row in df_subset.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**📅 {row.get('日時', '日付不明')} | 👤 {row.get('生徒名', '生徒名不明')} | 📚 {row.get('科目', '科目不明')} (👨‍🏫 {row.get('担当講師', '講師不明')})**")
                        has_any_comment = False
                        for col in comment_cols:
                            comment_text = str(row[col]).strip()
                            if comment_text and comment_text not in ["", "-", "nan", "None"]:
                                st.caption(f"**【{col}】**")
                                st.write(comment_text.replace('\n', '  \n'))
                                has_any_comment = True
                        if not has_any_comment:
                            st.caption("※特記すべきコメントはありませんでした。")

            if st.button("💬 この検索結果の『コメント詳細』を別枠で読む", icon="👁️", use_container_width=True, key="btn_lesson_comment"):
                show_comment_details(df_display)
        else:
            st.warning("⚠️ 表示項目が何も選択されていません。項目を1つ以上選択してください。")