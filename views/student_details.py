import streamlit as st
import pandas as pd 
import altair as alt 
import datetime 
import time 
import re 

from utils.g_sheets import (
    get_student_master,
    update_student_info,
    load_test_scores,
    get_student_self_study_points,
    get_student_quiz_records,
    get_quiz_master_dict,
    get_type_advice_dict
)
from utils.calc_logic import (
    calculate_ability_rank,
    calculate_motivation_rank,
    calculate_quiz_points
)
from utils.api_guard import robust_api_call

# 🌟 分離した2つのファイルをインポート！
from views.test_score_input import render_test_score_input
from views.test_score_view import render_test_score_view
from views.test_score_edit import render_test_score_edit

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_type_advice():
    return robust_api_call(get_type_advice_dict, fallback_value={})

def render_student_details_page(selected_student_option):
    if selected_student_option and " - " in selected_student_option:
        student_id = selected_student_option.split(" - ")[0]
        selected_student = selected_student_option.split(" - ")[1]
    else:
        student_id = "未設定"
        selected_student = selected_student_option
        
    tab_info, tab_input, tab_edit, tab_view = st.tabs(["👤 基本情報・カルテ", "✍️ テスト成績を入力", "🛠️ 成績データを修正", "📈 テスト成績推移を見る"])

    with tab_info:
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        info = {}
        if not df_students.empty and '生徒名' in df_students.columns:
            row = df_students[df_students['生徒名'] == selected_student]
            if not row.empty:
                info = row.iloc[0].to_dict()
        
        if student_id == "未設定" and "生徒ID" in info:
            student_id = str(info["生徒ID"]).strip()
            
        df_test = robust_api_call(load_test_scores, fallback_value=pd.DataFrame())
        
        df_student_tests = pd.DataFrame()
        if not df_test.empty and 'APIエラー発生' not in df_test.columns:
            df_student_tests = df_test[df_test['生徒名'] == selected_student]

        col_prof, col_graph = st.columns([1, 1])
        
        with col_prof:
            st.markdown(f"### 📝 {selected_student} さんのプロフィール")
            st.markdown(f"**🎓 学年**: {info.get('学年', '') or '未設定'}")
            
            disp_exam = info.get('受験区分', '')
            if disp_exam:
                st.markdown(f"**🔥 受験区分**: {disp_exam}")
            
            disp_school = info.get('学校区分', '')
            if disp_school:
                st.markdown(f"**🏫 学校区分**: {disp_school}")
            
            disp_types = str(info.get('タイプ', '')).replace('未設定', '').strip()
            
            st.markdown(f"**🏫 学校名**: {info.get('学校名', '') or '未設定'}")
            st.markdown(f"**🎯 志望校・目的**: {info.get('志望校・目的', '') or '未設定'}")
            st.markdown(f"**📚 受講科目**: {info.get('受講科目', '') or '未設定'}")
            st.markdown(f"**📋 契約コース**: {info.get('契約コース', '') or '未設定'}")
            
            disp_email = info.get('保護者メールアドレス', '')
            st.markdown(f"**✉️ 保護者メール**: {disp_email or '未設定'}")

            if disp_types:
                st.markdown(f"**🎯 生徒タイプ**: {disp_types.replace('、', ' / ')}")
                
                type_advice_dict = cached_get_type_advice()
                advices = []
                for t_key, t_adv in type_advice_dict.items():
                    if t_key in disp_types:
                        advices.append(f"・{t_adv}")
                
                if advices:
                    st.info("💡 **指導・面談アドバイス**\n\n" + "\n".join(advices))
            else:
                st.markdown("**🎯 生徒タイプ**: 未設定")
            
            if st.session_state.get('role') in ['admin', 'owner', 'head_teacher']:
                with st.expander("✏️ 基本情報を編集する (教室長のみ)"):
                    with st.form("edit_student_info_form"):
                        new_grade = st.text_input("学年 (例: 中2)", value=info.get('学年', ''))
                        
                        c_ex1, c_ex2 = st.columns(2)
                        
                        exam_opts = ["", "受験生"]
                        current_exam = str(info.get('受験区分', '')).replace('未設定', '')
                        ex_idx = exam_opts.index(current_exam) if current_exam in exam_opts else 0
                        new_exam = c_ex1.selectbox("🔥 受験区分", exam_opts, index=ex_idx)

                        school_opts = ["", "公立", "私立・国立"]
                        current_sch_type = str(info.get('学校区分', '')).replace('未設定', '')
                        sch_idx = school_opts.index(current_sch_type) if current_sch_type in school_opts else 0
                        new_school_type = c_ex2.selectbox("🏫 学校区分", school_opts, index=sch_idx)
                        
                        new_school = st.text_input("学校名", value=info.get('学校名', ''))
                        new_target = st.text_input("志望校・通塾目的", value=info.get('志望校・目的', ''))
                        new_subjects = st.text_input("受講科目 (例: 英語, 数学)", value=info.get('受講科目', ''))
                        
                        new_parent_email = st.text_input("✉️ 保護者メールアドレス", value=info.get('保護者メールアドレス', ''))

                        st.markdown("##### 📋 契約コース (回数/月)")
                        raw_course = str(info.get('契約コース', ''))
                        
                        b_match = re.search(r'Bコース[:：](\d+)', raw_course)
                        q_match = re.search(r'Qコース[:：](\d+)', raw_course)
                        b_default = int(b_match.group(1)) if b_match else None
                        q_default = int(q_match.group(1)) if q_match else None
                        
                        cc1, cc2 = st.columns(2)
                        b_val = cc1.number_input("Bコース", min_value=0, value=b_default, step=1)
                        q_val = cc2.number_input("Qコース", min_value=0, value=q_default, step=1)                    
                        
                        course_parts = []
                        if b_val and b_val > 0:
                            course_parts.append(f"Bコース:{b_val}")
                        if q_val and q_val > 0:
                            course_parts.append(f"Qコース:{q_val}")
                        new_contract_str = "、".join(course_parts)
                            
                        type_opts = ["充実", "訓練", "実用", "関係", "自尊", "報酬"]

                        current_types = str(info.get('タイプ', '')).replace('未設定', '').split('、')
                        current_types = [t for t in current_types if t in type_opts]

                        new_types = st.multiselect("🎯 生徒タイプ（複数選択可）", type_opts, default=current_types)

                        if st.form_submit_button("💾 基本情報を保存", type="primary"):
                            new_type_str = "、".join(new_types)
                            
                            with st.spinner("☁️ 情報を保存中...（混雑時は自動で再試行します）"):
                                def _update_info():
                                    update_student_info(
                                        student_id,
                                        selected_student, 
                                        new_grade, 
                                        new_school, 
                                        new_target, 
                                        new_subjects, 
                                        info.get('能力', 3), 
                                        info.get('やる気', 3), 
                                        info.get('内申点', 3), 
                                        info.get('最新偏差値', 50), 
                                        info.get('宿題履行率', 100),
                                        new_exam,        
                                        new_school_type,
                                        new_contract_str,
                                        new_type_str,
                                        parent_email=new_parent_email.strip()
                                    )
                                    return True
                                
                                success = robust_api_call(_update_info, fallback_value=False)
                                
                                if success:
                                    st.cache_data.clear() 
                                    st.success(f"基本情報を保存しました！")
                                    time.sleep(1.5) 
                                    st.rerun()
                                else:
                                    st.error("通信エラーが発生しました。もう一度お試しください。")
            else:
                st.info("※プロフィールの編集は教室長のみ可能です。")

        with col_graph:
            st.markdown("### 🧭 科目別：能力 × やる気 マトリクス")
            selected_subject = st.selectbox("📊 分析する科目を選択", ["英語", "数学", "国語", "理科", "社会"])
            
            latest_dev, latest_naishin = 50.0, 3
            
            if not df_student_tests.empty:
                df_moshi = df_student_tests[df_student_tests['テスト種別'] == "外部模試"]
                if not df_moshi.empty and f"{selected_subject} 偏差値" in df_moshi.columns:
                    latest_dev_val = df_moshi.iloc[-1][f"{selected_subject} 偏差値"]
                    if pd.notna(latest_dev_val) and str(latest_dev_val).replace('.','',1).isdigit():
                        latest_dev = float(latest_dev_val)
                
                df_naishin = df_student_tests[df_student_tests['テスト種別'] == "通知表（内申点）"]
                if not df_naishin.empty and f"{selected_subject} 内申" in df_naishin.columns:
                    latest_naishin_val = df_naishin.iloc[-1][f"{selected_subject} 内申"]
                    if pd.notna(latest_naishin_val) and str(latest_naishin_val).isdigit():
                        latest_naishin = int(latest_naishin_val)

            st.caption(f"💡 【自動参照】最新偏差値: **{latest_dev}** / 最新内申点: **{latest_naishin}**")
            
            raw_hw_rate = str(info.get('宿題履行率', '0.0')).replace('%', '').strip()
            try: 
                current_hw_rate = float(raw_hw_rate)
            except ValueError: 
                current_hw_rate = 0.0
                
            quiz_master = robust_api_call(get_quiz_master_dict, fallback_value={})
            quiz_records = robust_api_call(lambda: get_student_quiz_records(selected_student), fallback_value=[])
            total_quiz_pts = 0
            
            for record in quiz_records:
                pts = calculate_quiz_points(
                    score=record.get("score", 0), 
                    quiz_name=record.get("quiz_name", ""), 
                    quiz_master_dict=quiz_master
                )
                total_quiz_pts += pts
            
            self_study_pts = robust_api_call(lambda: get_student_self_study_points(selected_student), fallback_value=0)
            current_motivation = calculate_motivation_rank(current_hw_rate, total_quiz_pts, self_study_pts)
            
            st.caption(f"🔥 獲得ポイント ｜ 小テスト: **{total_quiz_pts} pt** / 自習: **{self_study_pts} pt**")
            
            ability = calculate_ability_rank(latest_naishin, latest_dev)
            
            df_coord = pd.DataFrame({"生徒": [selected_student], "能力 (X)": [ability], "やる気 (Y)": [current_motivation]})
            
            chart = alt.Chart(df_coord).mark_circle(size=800, color="#FF4B4B").encode(
                x=alt.X('能力 (X)', scale=alt.Scale(domain=[1, 5]), title="🧠 能力 (1〜5)"),
                y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[1, 5]), title="🔥 やる気 (1〜5)"),
                tooltip=['生徒', '能力 (X)', 'やる気 (Y)']
            ).properties(height=300)
            
            rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(x='x')
            rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(y='y')
            st.altair_chart(chart + rule_x + rule_y, use_container_width=True)

    with tab_input:
        render_test_score_input(selected_student)
        
    with tab_edit:
        render_test_score_edit(selected_student, df_student_tests)

    with tab_view:
        render_test_score_view(df_student_tests)