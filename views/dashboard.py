import streamlit as st
import pandas as pd
import altair as alt
import datetime 
import time 
import random
import re

# 🌟 api_guard.py から robust_api_call を呼び出す
from utils.api_guard import robust_api_call 

# 🌟 変更: 不要な関数を削り、マスター取得関数(get_student_master)と統合ログ(get_all_logs)を追加！
from utils.g_sheets import (
    get_student_master,
    get_all_logs,
    load_quiz_records,
    get_quiz_maker_sheets,
    get_student_self_study_points,
    load_test_scores
)
from utils.calc_logic import (
    calculate_quiz_points,
    calculate_ability_rank,
    calculate_motivation_rank,
    calc_pages_from_text
)

def render_dashboard_page():
    st.subheader("🌐 クラス全体ダッシュボード") 

    today = datetime.date.today()
    month_options = [(today - datetime.timedelta(days=i*30)).strftime("%Y年%m月") for i in range(12)]
    month_options.insert(0, "全期間") 

    all_grades = ["すべて"]
    all_subjects = ["すべて"]
    
    # 🌟 変更: 生徒マスター(DataFrame)を1回だけ読み込む！
    with st.spinner("☁️ 生徒基本データを一括読み込み中...（通信は1回だけ！一瞬で終わります🚀）"):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        if df_students.empty:
            st.warning("生徒データが見つかりません。設定シートを確認してください。")
            return
            
        for _, row in df_students.iterrows():
            grade = row.get('学年', '未設定')
            if grade not in all_grades and grade != "未設定" and str(grade).strip() != "":
                all_grades.append(grade)
                
            subject_raw = str(row.get('受講科目', '未設定'))
            if subject_raw != "未設定" and subject_raw.strip() != "":
                for sub in subject_raw.replace('、', ',').split(','):
                    sub = sub.strip()
                    if sub and sub not in all_subjects:
                        all_subjects.append(sub)
            
    with st.form("dashboard_filter_form"):
        selected_period = st.selectbox("📅 集計期間を選択", month_options)
        
        col1, col2 = st.columns(2)
        with col1:
            selected_grade = st.selectbox("🎯 学年で絞り込み", all_grades)
        with col2:
            selected_subject = st.selectbox("📚 科目で絞り込み", all_subjects)
            
        submit_button = st.form_submit_button("🚀 この条件で集計を開始する")

    if not submit_button:
        st.info("👆 上のメニューから条件を選んで、「集計を開始する」ボタンを押してください。")
        return
    
    # 🌟 ターゲット生徒のリストアップ（生徒IDと情報も一緒に保持して使い回す）
    target_students = []
    for _, row in df_students.iterrows():
        match_grade = (selected_grade == "すべて" or row.get('学年') == selected_grade)
        student_subject_str = str(row.get('受講科目', ''))
        match_subject = (selected_subject == "すべて" or selected_subject in student_subject_str)
        
        if match_grade and match_subject:
            target_students.append({
                "id": str(row.get('生徒ID', '')).strip(),
                "name": str(row.get('生徒名', '')).strip(),
                "hw_rate": str(row.get('宿題履行率', '0.0')),
                "info": row 
            })

    if not target_students:
        st.warning("該当する生徒がいません。")
        return

    st.markdown(f"**🗺️ 教室全体 俯瞰マトリクス ({selected_grade} / {selected_subject})**")
    
    matrix_placeholder = st.empty()

    current_month_str = datetime.date.today().strftime("%Y年%m月")
    summary_data = []
    matrix_data = []

    # 🌟 変更: ループの外で、すべての必要なデータを一括取得！！（これが超高速化の鍵）
    with st.spinner('☁️ 授業ログ統合・小テスト・模試データを一括取得中...（超高速処理🚀）'):
        df_all_logs = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
        if not df_all_logs.empty and '日時' in df_all_logs.columns and 'APIエラー発生' not in df_all_logs.columns:
            df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')

        df_all_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
        if not df_all_quizzes.empty and '日時' in df_all_quizzes.columns and 'APIエラー発生' not in df_all_quizzes.columns:
            df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')

        quiz_master_dict = robust_api_call(get_quiz_maker_sheets, fallback_value={})
        df_all_tests = robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

    with st.spinner(f'☁️ {current_month_str} のデータを集計中...'):
        progress_bar_data = st.progress(0)
        total_targets = len(target_students)
        
        for i, student in enumerate(target_students):
            s_id = student["id"]
            s_name = student["name"]
            
            # 🌟 変更: 通信せず、事前に取得した統合シート(df_all_logs)から生徒IDで抜き出すだけ！
            df_personal = pd.DataFrame()
            if not df_all_logs.empty:
                if s_id and '生徒ID' in df_all_logs.columns:
                    df_personal = df_all_logs[df_all_logs['生徒ID'].astype(str) == s_id].copy()
                elif '名前' in df_all_logs.columns: # IDが無い場合の念のためのフォールバック
                    df_personal = df_all_logs[df_all_logs['名前'] == s_name].copy()

            # 小テスト
            if not df_all_quizzes.empty and '名前' in df_all_quizzes.columns:
                df_student_quizzes = df_all_quizzes[df_all_quizzes['名前'] == s_name].copy()
            else:
                df_student_quizzes = pd.DataFrame()
            
            adv_pages = 0
            avg_score = None
            total_quiz_pts = 0

            if not df_student_quizzes.empty:
                if selected_period == "全期間":
                    q_filtered = df_student_quizzes
                else:
                    q_filtered = df_student_quizzes[df_student_quizzes['日時'].dt.strftime("%Y年%m月") == selected_period]

                if not q_filtered.empty and '点数' in q_filtered.columns:
                    valid_scores = []
                    for index, row in q_filtered.iterrows():
                        score_val = row['点数']
                        quiz_name = row.get('テキスト', '') 

                        if pd.isna(score_val) or str(score_val).strip() == "":
                            continue
                            
                        try:
                            numeric_score = float(score_val)
                            valid_scores.append(numeric_score)
                            total_quiz_pts += calculate_quiz_points(numeric_score, quiz_name, quiz_master_dict)
                        except ValueError:
                            pass 

                    if valid_scores:
                        avg_score = sum(valid_scores) / len(valid_scores)
            
            # 自習ポイント（※ここは今後の改修で一括取得にする余地がありますが、今回はこのまま）
            self_study_pts = robust_api_call(get_student_self_study_points, s_name, fallback_value=0)

            final_total_points = total_quiz_pts + self_study_pts

            # --- 🌟 進捗の計算 (統合シートから抽出したデータを使用) ---
            if not df_personal.empty:
                df_p_filtered = df_personal.copy()

                if selected_subject != "すべて" and '科目' in df_p_filtered.columns:
                    df_p_filtered = df_p_filtered[df_p_filtered['科目'].str.contains(selected_subject, na=False)]
                
                if selected_period != "全期間" and '日時' in df_p_filtered.columns:
                    df_p_filtered = df_p_filtered[df_p_filtered['日時'].dt.strftime("%Y年%m月") == selected_period]
                    
                try:
                    # 🌟 統合シートの「終了ページ」列を処理
                    col_target = '終了ページ' if '終了ページ' in df_p_filtered.columns else 'ページ数' if 'ページ数' in df_p_filtered.columns else None
                    if col_target:
                        df_p_filtered['今回の進捗'] = df_p_filtered[col_target].apply(calc_pages_from_text)
                        adv_pages = int(df_p_filtered['今回の進捗'].sum())
                except Exception as e:
                    adv_pages = 0

            # ① 能力 (X) を計算する
            latest_dev, latest_naishin = 50.0, 3 
            if not df_all_tests.empty and '生徒名' in df_all_tests.columns and 'APIエラー発生' not in df_all_tests.columns:
                df_s = df_all_tests[df_all_tests['生徒名'] == s_name]
                if not df_s.empty:
                    df_moshi = df_s[df_s['テスト種別'] == "外部模試"]
                    if not df_moshi.empty and f"{selected_subject} 偏差値" in df_moshi.columns:
                        val = df_moshi.iloc[-1][f"{selected_subject} 偏差値"]
                        if pd.notna(val) and str(val).replace('.','',1).isdigit(): latest_dev = float(val)
                    
                    df_naishin = df_s[df_s['テスト種別'] == "通知表（内申点）"]
                    if not df_naishin.empty and f"{selected_subject} 内申" in df_naishin.columns:
                        val = df_naishin.iloc[-1][f"{selected_subject} 内申"]
                        if pd.notna(val) and str(val).isdigit(): latest_naishin = int(val)
            
            ability_x = calculate_ability_rank(latest_naishin, latest_dev)

            # ② やる気 (Y) を計算する
            raw_hw_rate = str(student["hw_rate"]).replace('%', '').strip()
            try: hw_rate = float(raw_hw_rate)
            except ValueError: hw_rate = 0.0
            
            motivation_y = calculate_motivation_rank(hw_rate, final_total_points, self_study_pts)

            # ③ マトリクス用のリストに追加
            matrix_data.append({
                "生徒名": s_name,
                "能力 (X)": ability_x,
                "やる気 (Y)": motivation_y
            })

            summary_data.append({
                "生徒名": s_name, 
                "選択期間の進捗(ページ)": adv_pages, 
                "選択期間の平均点": round(avg_score, 1) if pd.notna(avg_score) else None, 
                "選択期間の獲得ポイント": final_total_points 
            })
            
            progress_bar_data.progress((i + 1) / total_targets)
            
        progress_bar_data.empty()

    if matrix_data:
        df_matrix = pd.DataFrame(matrix_data)
        chart = alt.Chart(df_matrix).mark_circle(size=400, opacity=0.8, color="#1E90FF").encode(
            x=alt.X('能力 (X)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🧠 能力 (1〜5)"),
            y=alt.Y('やる気 (Y)', scale=alt.Scale(domain=[0.5, 5.5]), axis=alt.Axis(values=[1, 2, 3, 4, 5]), title="🔥 やる気 (1〜5)"),
            tooltip=['生徒名', '能力 (X)', 'やる気 (Y)']
        )
        text = chart.mark_text(align='left', baseline='middle', dx=15, dy=0, fontSize=12, fontWeight='bold').encode(text='生徒名')
        rule_x = alt.Chart(pd.DataFrame({'x': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(x='x')
        rule_y = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='gray', strokeDash=[5,5]).encode(y='y')

        matrix_placeholder.altair_chart(chart + text + rule_x + rule_y, use_container_width=True)    

    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        st.markdown(f"**🏆 累計獲得ポイント ランキング TOP3 ({selected_grade} / {selected_subject})**")
        df_ranking = df_summary.sort_values(by="選択期間の獲得ポイント", ascending=False).head(3).reset_index(drop=True)
        
        cols = st.columns(3)
        colors, medals = ["#FFD700", "#C0C0C0", "#CD7F32"], ["🥇 1位", "🥈 2位", "🥉 3位"]
        
        for i in range(min(3, len(df_ranking))):
            with cols[i]:
                st.markdown(f"<div style='background-color:{colors[i]}15; padding:15px; border-radius:10px; border: 2px solid {colors[i]}; text-align:center;'><h3>{medals[i]}</h3><h2>{df_ranking.loc[i, '生徒名']}</h2><h1>{df_ranking.loc[i, '選択期間の獲得ポイント']} <span style='font-size:0.4em;'>pt</span></h1></div>", unsafe_allow_html=True)

        st.divider()
        st.markdown(f"**📊 選択期間の状況 ({selected_grade} / {selected_subject})**")
        c1, c2 = st.columns(2)
        
        with c1: 
            st.write("**📖 進捗ランキング**")
            st.dataframe(df_summary.sort_values(by="選択期間の進捗(ページ)", ascending=False)[["生徒名", "選択期間の進捗(ページ)"]], hide_index=True, use_container_width=True)
            
        with c2: 
            st.write("**💯 小テスト平均点**")
            st.dataframe(df_summary.dropna(subset=["選択期間の平均点"]).sort_values(by="選択期間の平均点", ascending=False)[["生徒名", "選択期間の平均点"]], hide_index=True, use_container_width=True)