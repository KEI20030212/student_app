import streamlit as st
import pandas as pd
from datetime import date
import time
from utils.g_sheets import add_school_homework_multi
from utils.api_guard import robust_api_call

def render_hw_add(df_students):
    st.subheader("➕ 学校・学年を指定して一括登録")
    st.info("課題内容を改行して入力すると、一度に複数の課題を登録できます。")
    
    if df_students.empty:
        st.warning("生徒データが取得できません。通信エラーか、設定_生徒情報シートを確認してください。")
        return
    if '学校名' not in df_students.columns:
        st.error("「設定_生徒情報」シートに「学校名」列が見つかりません。")
        return

    valid_schools = sorted([s for s in df_students['学校名'].unique() if str(s).strip() != ""])
    valid_grades = sorted([g for g in df_students['学年'].unique() if str(g).strip() != ""]) if '学年' in df_students.columns else []
    
    with st.form("simple_add_form"):
        current_year = date.today().year if date.today().month >= 4 else date.today().year - 1
        
        st.markdown("##### 📅 時期・テスト設定")
        c_y, c_t, c_k = st.columns(3)
        with c_y: nendo = st.number_input("年度", value=current_year, step=1)
        with c_t: gakki = st.selectbox("学期", ["1学期", "2学期", "3学期", "前期", "後期", "夏休み", "冬休み", "春休み", "その他"])
        with c_k: test_type = st.selectbox("期間・種別", ["中間テスト", "期末テスト", "実力テスト", "課題テスト", "長期休み課題", "その他"])
        
        st.divider()
        st.markdown("##### 🏫 ターゲット設定")
        col_f1, col_f2 = st.columns(2)
        with col_f1: target_school = st.selectbox("🏫 対象の学校名", valid_schools)
        with col_f2: target_grade = st.selectbox("🎯 対象の学年", valid_grades)
        
        target_student_list = df_students[(df_students['学校名'] == target_school) & (df_students['学年'] == target_grade)]['生徒名'].tolist()
        st.write(f"💡 **対象生徒:** {', '.join(target_student_list) if target_student_list else '該当者なし'}")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1: subject = st.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "音楽", "美術", "保体", "技家", "その他"])
        with col2: deadline = st.date_input("提出期限", date.today())
        
        content_text = st.text_area("課題内容 (1行に1つずつ入力)", placeholder="数学ワーク P10-P20\n計算プリント No.5\n英単語テストの練習")
        memo = st.text_area("メモ (全課題に共通して保存されます)")
        
        if st.form_submit_button("一括登録する！", use_container_width=True):
            task_list = [t.strip() for t in content_text.split("\n") if t.strip()]
            if not target_student_list: st.error(f"{target_school}の{target_grade}に該当する生徒がいません。")
            elif not task_list: st.error("課題内容を1つ以上入力してください！")
            else:
                with st.spinner("一括登録中..."):
                    result = robust_api_call(add_school_homework_multi, nendo, gakki, test_type, target_student_list, subject, task_list, deadline, memo, fallback_value=(False, "通信エラーが発生しました。"))
                    if result[0]:
                        st.success(f"【{target_school} {target_grade}】の{len(target_student_list)}名に、{len(task_list)}個の課題を登録しました！")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"登録失敗: {result[1]}")