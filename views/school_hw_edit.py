import streamlit as st
import pandas as pd
from datetime import date
import time
from utils.g_sheets import update_school_homework_detail
from utils.api_guard import robust_api_call

def render_hw_edit(df_hw, df_students):
    st.subheader("🛠️ 登録済み課題の修正")
    st.write("登録済みの課題内容や提出期限を後から修正できます。")
    
    if df_hw.empty or 'APIエラー発生' in df_hw.columns:
        st.info("修正できる課題データがありません。")
        return
    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return
        
    for col in ['年度', '学期', 'テスト種別']:
        if col not in df_hw.columns: df_hw[col] = ""
            
    df_merged = pd.merge(df_hw, df_students[['生徒名', '学校名', '学年']], on='生徒名', how='left')
    
    st.markdown("##### 🔍 絞り込み条件")
    c_f1, c_f2 = st.columns(2)
    f_school = c_f1.selectbox("🏫 学校名", ["すべて"] + sorted([s for s in df_merged['学校名'].unique() if str(s) != 'nan' and str(s).strip() != ""]), key="f_sch")
    f_grade = c_f2.selectbox("🎯 学年", ["すべて"] + sorted([g for g in df_merged['学年'].unique() if str(g) != 'nan' and str(g).strip() != ""]), key="f_grd")
    
    c_f3, c_f4 = st.columns(2)
    f_term = c_f3.selectbox("📅 学期", ["すべて"] + sorted([t for t in df_merged['学期'].unique() if str(t) != 'nan' and str(t).strip() != ""]), key="f_term")
    f_test = c_f4.selectbox("🔥 テスト種別", ["すべて"] + sorted([t for t in df_merged['テスト種別'].unique() if str(t) != 'nan' and str(t).strip() != ""]), key="f_test")
    
    filtered_df = df_merged.copy()
    if f_school != "すべて": filtered_df = filtered_df[filtered_df['学校名'] == f_school]
    if f_grade != "すべて": filtered_df = filtered_df[filtered_df['学年'] == f_grade]
    if f_term != "すべて": filtered_df = filtered_df[filtered_df['学期'] == f_term]
    if f_test != "すべて": filtered_df = filtered_df[filtered_df['テスト種別'] == f_test]
    
    st.divider()
    if filtered_df.empty:
        st.info("条件に一致する課題は見つかりませんでした。")
        return
        
    students_in_filter = sorted(filtered_df['生徒名'].unique())
    st.success(f"条件に一致する生徒が {len(students_in_filter)}名 見つかりました。アコーディオンを開いて編集してください。")
    
    for student in students_in_filter:
        student_tasks = filtered_df[filtered_df['生徒名'] == student]
        with st.expander(f"👤 {student} の課題を修正（{len(student_tasks)}件）", expanded=False):
            for idx, row in student_tasks.iterrows():
                with st.container(border=True):
                    with st.form(key=f"edit_form_{idx}", border=False):
                        c_e1, c_e2, c_e3 = st.columns([2, 3, 2])
                        edit_subj = c_e1.text_input("教科", value=row.get('教科', ''), key=f"e_subj_{idx}")
                        edit_task = c_e2.text_input("課題内容", value=row.get('課題内容', ''), key=f"e_task_{idx}")
                        try: def_date = pd.to_datetime(row.get('提出期限')).date()
                        except: def_date = date.today()
                        edit_dead = c_e3.date_input("提出期限", value=def_date, key=f"e_dead_{idx}")
                        
                        c_e4, c_e5 = st.columns([4, 1])
                        edit_memo = c_e4.text_input("メモ", value=row.get('メモ', ''), key=f"e_memo_{idx}")
                        
                        if st.form_submit_button("💾 保存", use_container_width=True):
                            with st.spinner("更新中..."):
                                success = robust_api_call(update_school_homework_detail, row.name + 2, edit_subj, edit_task, edit_dead, edit_memo, fallback_value=False)
                                if success:
                                    st.success("✅ 更新しました！")
                                    st.cache_data.clear()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ 更新エラー")