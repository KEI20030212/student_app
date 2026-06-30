import streamlit as st
import pandas as pd
import datetime
import time
import re 

from utils.g_sheets import (
    get_student_master, 
    get_quiz_master_dict,                
    save_quizzes_to_dedicated_sheet,  
    load_quiz_records,
    get_textbook_master
)
from utils.api_guard import robust_api_call

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600)  
def cached_get_quiz_details():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

def cached_load_all_quizzes():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
  
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("実施した小テストの結果を入力・確認できるページです🎨")

    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    
    if df_students.empty:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    
    selected_student_option = st.selectbox("👤 生徒を選択", student_options, index=None, placeholder="-- 生徒を選択 --")
    
    if selected_student_option is None:
        st.stop()

    student_id = selected_student_option.split(" - ")[0]
    student_name = selected_student_option.split(" - ")[1]

    quiz_details = cached_get_quiz_details()
    
    quiz_names = []
    for key in quiz_details.keys():
        if "_" in key:
            q_name = key.split("_", 1)[0]
            if q_name not in quiz_names:
                quiz_names.append(q_name)

    with st.expander("📝 小テスト結果を登録する"):
        st.write(f"**{student_name}** さんの結果を入力します。") 
        
        if not quiz_names:
            st.warning("「設定_小テスト一覧」のデータが取得できません。")
        else:
            target_quiz = st.selectbox("📝 実施した小テスト名", quiz_names, key="input_target_quiz")
            
            max_score = 100
            if target_quiz:
                matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{target_quiz}_")]
                if matched_marks:
                    max_score = int(pd.Series(matched_marks).mode()[0])
            
            with st.form("quiz_input_form"):
                col1, col2 = st.columns(2)
                target_unit = col1.number_input("📖 単元・回", min_value=1, value=1, step=1)
                
                score = col2.number_input(f"💯 点数 (満点: {max_score})", min_value=0, max_value=max_score, value=max_score, step=1)
                
                test_date = st.date_input("📅 実施日", datetime.date.today())
                
                submit_quiz = st.form_submit_button("この内容で記録する ✨", type="primary")
                
                if submit_quiz:
                    if target_unit < 1:
                        st.error("⚠️ 「単元・回」を入力してください。")
                    else:
                        with st.spinner("記録中..."):
                            quiz_row_data = [[
                                test_date.strftime("%Y/%m/%d"), 
                                student_name,  
                                target_quiz,  
                                target_unit,  
                                score,
                                "", 
                                "自習"
                            ]]
                            
                            success = robust_api_call(
                                save_quizzes_to_dedicated_sheet,
                                quiz_row_data,
                                fallback_value=False
                            )
                            
                            if success:
                                st.success(f"【{target_quiz} - {target_unit}】を {score}点で記録しました！")
                                # 🌟 修正2：大元の関数（load_quiz_records）のキャッシュを確実に破壊する！
                                load_quiz_records.clear() 
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("記録に失敗しました。")

    st.divider()

    # ==========================================
    # 🌟 習熟度マップの表示ロジック
    # ==========================================
    with st.spinner("習熟度データを集計中..."):
        df_all_quizzes = cached_load_all_quizzes()
        textbook_master = cached_get_textbook_master()
        
        if "APIエラー発生" in df_all_quizzes.columns:
            st.error("データの取得中にエラーが発生しました。")
            st.stop()
            
        if not df_all_quizzes.empty and '名前' in df_all_quizzes.columns:
            df_quiz = df_all_quizzes[df_all_quizzes['名前'] == student_name].copy()
        else:
            df_quiz = pd.DataFrame()
        
        if df_quiz.empty:
            st.info("小テストの記録がまだありません。結果を登録するとここに表が表示されます。")
            st.stop()

        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz = df_quiz.dropna(subset=['点数']).copy()
        
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回実施日: **{last_date}**")

        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'テキスト': '小テスト名', '点数': '最高点数'})

        quiz_list = best_scores['小テスト名'].unique().tolist()
        
        if not quiz_list:
            st.stop()
            
        tabs = st.tabs(quiz_list)

        def sort_key(c):
            nums = re.findall(r'\d+', str(c))
            return int(nums[0]) if nums else 999

        for i, q_name in enumerate(quiz_list):
            with tabs[i]: 
                df_display = best_scores[best_scores['小テスト名'] == q_name]
                
                pivot_df = df_display.pivot_table(
                    index='小テスト名', 
                    columns='単元', 
                    values='最高点数', 
                    aggfunc='max'
                )
                
                if pivot_df.empty:
                    continue

                pivot_df = pivot_df[sorted(pivot_df.columns.tolist(), key=sort_key)]

                col_mapping = {}
                t_master = textbook_master.get(q_name, {}) 
                
                for col in pivot_df.columns:
                    chap_str = str(col)
                    chap_name = t_master.get(chap_str, "")
                    if chap_name:
                        col_mapping[col] = f"{chap_str}: {chap_name}"
                    else:
                        col_mapping[col] = f"第{chap_str}回"
                        
                pivot_df = pivot_df.rename(columns=col_mapping)

                def add_icon(val):
                    if pd.isna(val) or val == "": return ""
                    
                    full_m = 100
                    matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_name}_")]
                    if matched_marks:
                        full_m = int(pd.Series(matched_marks).mode()[0])
                            
                    try:
                        v = float(val)
                        ratio = v / full_m if full_m > 0 else 0
                        if ratio >= 1.0: return f"👑 {int(v)}"
                        elif ratio >= 0.8: return f"🟢 {int(v)}"
                        elif ratio >= 0.2: return f"🟡 {int(v)}"
                        else: return f"🔴 {int(v)}"
                    except:
                        return str(val)

                styled_display = pivot_df.copy()
                for col in styled_display.columns:
                    styled_display[col] = styled_display[col].apply(add_icon)

                def color_bg(v):
                    if "👑" in str(v): return 'background-color: #fffacd; color: #000; font-weight: bold;'
                    if "🟢" in str(v): return 'background-color: #c6efce; color: #006100;'
                    if "🟡" in str(v): return 'background-color: #ffeb9c; color: #9c6500;'
                    if "🔴" in str(v): return 'background-color: #ffc7ce; color: #9c0006;'
                    return ''

                try:
                    st.dataframe(styled_display.style.applymap(color_bg), use_container_width=True)
                except AttributeError:
                    st.dataframe(styled_display.style.map(color_bg), use_container_width=True)