import streamlit as st
import pandas as pd 
import altair as alt 
import datetime 
import time 
import re # 🌟 文字列から数字を抽出するために追加

# 🌟 変更: get_student_info を削除し、get_student_master に変更
from utils.g_sheets import (
    get_student_master,
    update_student_info,
    save_test_score,
    load_test_scores,
    get_student_self_study_points,
    get_student_quiz_records,
    get_quiz_master_dict
)
from utils.calc_logic import (
    calculate_ability_rank,
    calculate_motivation_rank,
    calculate_quiz_points
)

# 🌟 APIガードをインポート
from utils.api_guard import robust_api_call

def render_student_details_page(selected_student_option):
    if selected_student_option and " - " in selected_student_option:
        student_id = selected_student_option.split(" - ")[0]
        selected_student = selected_student_option.split(" - ")[1]
    else:
        student_id = "未設定"
        selected_student = selected_student_option
        
    tab_info, tab_input, tab_view = st.tabs(["👤 基本情報・カルテ", "✍️ テスト成績を入力", "📈 テスト成績推移を見る"])

    with tab_info:
        # 🌟 劇的改善: 重い個別取得をやめて、キャッシュされたマスターから一瞬で情報を探す！
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        info = {}
        if not df_students.empty and '生徒名' in df_students.columns:
            row = df_students[df_students['生徒名'] == selected_student]
            if not row.empty:
                info = row.iloc[0].to_dict()
        
        if student_id == "未設定" and "生徒ID" in info:
            student_id = str(info["生徒ID"]).strip()
            
        # 🌟 APIエラー対策付きの読み込み
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
            
            st.markdown(f"**🏫 学校名**: {info.get('学校名', '') or '未設定'}")
            st.markdown(f"**🎯 志望校・目的**: {info.get('志望校・目的', '') or '未設定'}")
            st.markdown(f"**📚 受講科目**: {info.get('受講科目', '') or '未設定'}")
            # 🌟 追加：契約コースの表示
            st.markdown(f"**📋 契約コース**: {info.get('契約コース', '') or '未設定'}")
            
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
                        
                        # 🌟 追加：契約コースの入力欄
                        st.markdown("##### 📋 契約コース (回数/月)")
                        raw_course = str(info.get('契約コース', ''))
                        
                        # スプレッドシートの文字列から数字を自動抽出（パース）
                        b_match = re.search(r'Bコース[:：](\d+)', raw_course)
                        q_match = re.search(r'Qコース[:：](\d+)', raw_course)
                        b_default = int(b_match.group(1)) if b_match else None
                        q_default = int(q_match.group(1)) if q_match else None
                        
                        cc1, cc2 = st.columns(2)
                        b_val = cc1.number_input("Bコース", min_value=0, value=b_default, step=1)
                        q_val = cc2.number_input("Qコース", min_value=0, value=q_default, step=1)
                        
                        if st.form_submit_button("💾 基本情報を保存", type="primary"):
                            
                            # 🌟 追加：入力された数字をスプレッドシート保存用の文字列に再結合
                            course_parts = []
                            if b_val and b_val > 0:
                                course_parts.append(f"Bコース:{b_val}")
                            if q_val and q_val > 0:
                                course_parts.append(f"Qコース:{q_val}")
                            new_contract_str = "、".join(course_parts)

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
                                        new_contract_str # 🌟 追加：結合した契約コースの文字列を渡す
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
        with st.container(border=True):
            st.write(f"**{selected_student}** さんのテスト結果・内申点を入力します。")
            
            c1, c2 = st.columns(2)
            date = c1.date_input("実施日", datetime.date.today())
            test_type = c2.selectbox("📝 テスト種別", ["定期テスト(中間など)", "期末テスト", "外部模試", "通知表（内申点）", "その他"])

            if test_type == "通知表（内申点）":
                with st.form("naishin_input_form"):
                    st.info("各科目の内申点（1〜5）と態度（A〜C）を入力してください。")
                    n1, n2, n3, n4, n5 = st.columns(5)
                    
                    n_eng = n1.number_input("英語 内申", 1, 5, value=None)
                    att_eng = n1.selectbox("英語 態度", ["", "A", "B", "C"], index=0)
                    
                    n_math = n2.number_input("数学 内申", 1, 5, value=None)
                    att_math = n2.selectbox("数学 態度", ["", "A", "B", "C"], index=0)
                    
                    n_jpn = n3.number_input("国語 内申", 1, 5, value=None)
                    att_jpn = n3.selectbox("国語 態度", ["", "A", "B", "C"], index=0)
                    
                    n_sci = n4.number_input("理科 内申", 1, 5, value=None)
                    att_sci = n4.selectbox("理科 態度", ["", "A", "B", "C"], index=0)
                    
                    n_soc = n5.number_input("社会 内申", 1, 5, value=None)
                    att_soc = n5.selectbox("社会 態度", ["", "A", "B", "C"], index=0)
                    
                    st.divider()
                    nb1, nb2, nb3, nb4 = st.columns(4)
                    
                    n_pe = nb1.number_input("保体 内申", 1, 5, value=None)
                    att_pe = nb1.selectbox("保体 態度", ["", "A", "B", "C"], index=0)
                    
                    n_gika = nb2.number_input("技家 内申", 1, 5, value=None)
                    att_gika = nb2.selectbox("技家 態度", ["", "A", "B", "C"], index=0)
                    
                    n_art = nb3.number_input("美術 内申", 1, 5, value=None)
                    att_art = nb3.selectbox("美術 態度", ["", "A", "B", "C"], index=0)
                    
                    n_mus = nb4.number_input("音楽 内申", 1, 5, value=None)
                    att_mus = nb4.selectbox("音楽 態度", ["", "A", "B", "C"], index=0)
                    
                    submit_naishin = st.form_submit_button("💾 内申点を登録する", type="primary")
                    
                    if submit_naishin:
                        with st.spinner("☁️ 保存中...（混雑時は自動で再試行します）"):
                            def _save_naishin():
                                save_test_score(date, selected_student, test_type, n_eng, n_math, n_jpn, n_sci, n_soc, 
                                                None, None, None, None, None, None, None, 
                                                n_pe, n_gika, None, n_mus, n_art, is_naishin=True,
                                                att_eng=att_eng, att_math=att_math, att_jpn=att_jpn, 
                                                att_sci=att_sci, att_soc=att_soc, att_pe=att_pe, 
                                                att_gika=att_gika, att_art=att_art, att_mus=att_mus)
                                return True
                            
                            success = robust_api_call(_save_naishin, fallback_value=False)
                            
                            if success:
                                st.cache_data.clear()
                                st.success("内申点を登録しました！")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("通信エラーが発生しました。もう一度お試しください。")

            else:
                with st.form("test_score_input_form"):
                    with st.expander("⚙️ 各教科の満点設定"):
                        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                        m_eng = mc1.number_input("英 満点", 0, 100, 100)
                        m_math = mc2.number_input("数 満点", 0, 100, 100)
                        m_jpn = mc3.number_input("国 満点", 0, 100, 100)
                        m_sci = mc4.number_input("理 満点", 0, 100, 100)
                        m_soc = mc5.number_input("社 満点", 0, 100, 100)
                        
                        m_pe, m_tech, m_home, m_art, m_mus = 50, 50, 50, 50, 50
                        if test_type == "期末テスト":
                            mc6, mc7, mc8, mc9, mc10 = st.columns(5)
                            m_pe = mc6.number_input("保 満点", 0, 100, 50)
                            m_tech = mc7.number_input("技 満点", 0, 100, 50)
                            m_home = mc8.number_input("家 満点", 0, 100, 50)
                            m_art = mc9.number_input("美 満点", 0, 100, 50)
                            m_mus = mc10.number_input("音 満点", 0, 100, 50)

                    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                    eng = sc1.number_input(f"英語 (/{m_eng})", 0, m_eng, value=None)
                    math_score = sc2.number_input(f"数学 (/{m_math})", 0, m_math, value=None)
                    jpn = sc3.number_input(f"国語 (/{m_jpn})", 0, m_jpn, value=None)
                    sci = sc4.number_input(f"理科 (/{m_sci})", 0, m_sci, value=None)
                    soc = sc5.number_input(f"社会 (/{m_soc})", 0, m_soc, value=None)

                    dev_eng, dev_math, dev_jpn, dev_sci, dev_soc = None, None, None, None, None
                    if test_type == "外部模試":
                        st.divider()
                        st.markdown("##### 📊 偏差値の入力")
                        d1, d2, d3, d4, d5 = st.columns(5)
                        dev_eng = d1.number_input("英語 偏差値", 0.0, 90.0, value=None, step=0.1)
                        dev_math = d2.number_input("数学 偏差値", 0.0, 90.0, value=None, step=0.1)
                        dev_jpn = d3.number_input("国語 偏差値", 0.0, 90.0, value=None, step=0.1)
                        dev_sci = d4.number_input("理科 偏差値", 0.0, 90.0, value=None, step=0.1)
                        dev_soc = d5.number_input("社会 偏差値", 0.0, 90.0, value=None, step=0.1)

                    pe, tech, home, art, mus = None, None, None, None, None
                    if test_type == "期末テスト":
                        st.divider()
                        sc6, sc7, sc8, sc9, sc10 = st.columns(5)
                        pe = sc6.number_input(f"保体 (/{m_pe})", 0, m_pe, value=None)
                        tech = sc7.number_input(f"技術 (/{m_tech})", 0, m_tech, value=None)
                        home = sc8.number_input(f"家庭科 (/{m_home})", 0, m_home, value=None)
                        art = sc9.number_input(f"美術 (/{m_art})", 0, m_art, value=None)
                        mus = sc10.number_input(f"音楽 (/{m_mus})", 0, m_mus, value=None)

                    submit_test = st.form_submit_button("💾 この成績を登録する", type="primary")
                    
                    if submit_test:
                        with st.spinner("☁️ 保存中...（混雑時は自動で再試行します）"):
                            def _save_test():
                                save_test_score(date, selected_student, test_type, eng, math_score, jpn, sci, soc, 
                                                dev_eng, dev_math, dev_jpn, dev_sci, dev_soc, None, None, 
                                                pe, tech, home, mus, art, is_naishin=False)
                                return True
                            
                            success = robust_api_call(_save_test, fallback_value=False)
                            
                            if success:
                                st.cache_data.clear()
                                st.success("成績を登録しました！")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("通信エラーが発生しました。もう一度お試しください。")

    with tab_view:
        if not df_student_tests.empty:
            df_view = df_student_tests.copy()
            df_view['日時'] = pd.to_datetime(df_view['日時'])
            df_view = df_view.sort_values('日時')

            st.subheader("📊 成績・内申・態度 推移チャート")

            view_mode = st.radio("表示項目を選択してください", ["総合点・偏差値", "内申点・学習態度"], horizontal=True)

            if view_mode == "総合点・偏差値":
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**📈 総合点 推移**")
                    df_total = df_view[df_view['総合'] != "-"]
                    if not df_total.empty:
                        st.line_chart(df_total.set_index("日時")["総合"])
                    else:
                        st.caption("総合点のデータがありません。")

                with col2:
                    st.markdown("**📉 5科偏差値 推移**")
                    df_dev = df_view[df_view['偏差値_5科'] != "-"]
                    if not df_dev.empty:
                        st.line_chart(df_dev.set_index("日時")["偏差値_5科"])
                    else:
                        st.caption("偏差値のデータがありません。")

            else:  
                df_naishin_only = df_view[df_view['テスト種別'] == "通知表（内申点）"].copy()
                
                if df_naishin_only.empty:
                    st.info("内申点・態度のデータがまだ登録されていません。")
                else:
                    subjects = ["英語", "数学", "国語", "理科", "社会", "保体", "技家", "美術", "音楽"]
                    selected_subs = st.multiselect("表示する科目を選択", subjects, default=["英語", "数学", "国語"])

                    col_n, col_a = st.columns(2)

                    with col_n:
                        st.markdown("**🏫 内申点(1-5) 推移**")
                        plot_data_n = pd.DataFrame({"日時": df_naishin_only["日時"]})
                        for sub in selected_subs:
                            col_name = f"{sub} 内申"
                            if col_name in df_naishin_only.columns:
                                plot_data_n[sub] = pd.to_numeric(df_naishin_only[col_name], errors='coerce')
                        
                        st.line_chart(plot_data_n.set_index("日時"))

                    with col_a:
                        st.markdown("**🔥 学習態度(A-C) 推移**")
                        st.caption("※ A=3, B=2, C=1 として計算")
                        
                        att_map = {"A": 3, "B": 2, "C": 1}
                        plot_data_a = pd.DataFrame({"日時": df_naishin_only["日時"]})
                        
                        for sub in selected_subs:
                            col_name = f"{sub} 態度"
                            if col_name in df_naishin_only.columns:
                                plot_data_a[sub] = df_naishin_only[col_name].map(att_map)
                        
                        chart_a = alt.Chart(plot_data_a.melt("日時", var_name="科目", value_name="値")).mark_line(point=True).encode(
                            x='日時:T',
                            y=alt.Y('値:Q', scale=alt.Scale(domain=[1, 3]), axis=alt.Axis(values=[1, 2, 3], labelExpr="datum.value == 3 ? 'A' : datum.value == 2 ? 'B' : 'C'")),
                            color='科目:N',
                            tooltip=['日時', '科目', '値']
                        ).properties(height=300)
                        st.altair_chart(chart_a, use_container_width=True)

            st.divider()
            st.subheader("📋 成績履歴詳細")
            
            def color_attitude(val):
                if val == 'A': return 'background-color: #d1e7dd'
                if val == 'C': return 'background-color: #f8d7da'
                return ''

            st.dataframe(
                df_view.sort_values("日時", ascending=False),
                hide_index=True,
                use_container_width=True
            )
            
        else:
            st.info("まだ成績データがありません。")