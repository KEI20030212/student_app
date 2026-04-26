import streamlit as st
import pandas as pd 
import altair as alt 
import datetime 
import time 
import gspread # 🌟 APIエラー対策

from utils.g_sheets import (
    get_student_info,
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

def render_student_details_page(selected_student):
    # タブ作成
    tab_info, tab_input, tab_view = st.tabs(["👤 基本情報・カルテ", "✍️ テスト成績を入力", "📈 テスト成績推移を見る"])

    with tab_info:
        info = get_student_info(selected_student)
        
        # 🌟 APIエラー対策付きの読み込み
        df_test = pd.DataFrame()
        max_retries = 5
        for attempt in range(max_retries):
            try:
                df_test = load_test_scores()
                break
            except Exception:
                if attempt < max_retries - 1: 
                    time.sleep(2 ** attempt)
        
        df_student_tests = pd.DataFrame()
        if not df_test.empty:
            df_student_tests = df_test[df_test['生徒名'] == selected_student]

        col_prof, col_graph = st.columns([1, 1])
        
        with col_prof:
            st.markdown(f"### 📝 {selected_student} さんのプロフィール")
            st.markdown(f"**🎓 学年**: {info.get('学年', '未設定')}")
            st.markdown(f"**🏫 学校名**: {info.get('学校名', '未設定')}")
            st.markdown(f"**🎯 志望校・目的**: {info.get('志望校・目的', '未設定')}")
            st.markdown(f"**📚 受講科目**: {info.get('受講科目', '未設定')}")
            
            if st.session_state.get('role') == 'admin':
                with st.expander("✏️ 基本情報を編集する (教室長のみ)"):
                    # 🌟 st.form を使って、ボタンを押すまで通信しないようにする
                    with st.form("edit_student_info_form"):
                        new_grade = st.text_input("学年 (例: 中2)", value=info.get('学年', ''))
                        new_school = st.text_input("学校名", value=info.get('学校名', ''))
                        new_target = st.text_input("志望校・通塾目的", value=info.get('志望校・目的', ''))
                        new_subjects = st.text_input("受講科目 (例: 英語, 数学)", value=info.get('受講科目', ''))
                        
                        if st.form_submit_button("💾 基本情報を保存", type="primary"):
                            with st.spinner("☁️ 情報を保存中...（混雑時は自動で再試行します）"):
                                max_retries_save = 5
                                for attempt in range(max_retries_save):
                                    try:
                                        update_student_info(selected_student, new_grade, new_school, new_target, new_subjects, info.get('能力', 3), info.get('やる気', 3), info.get('内申点', 3), info.get('最新偏差値', 50), info.get('宿題履行率', 100))
                                        time.sleep(1) 
                                        st.cache_data.clear() 
                                        st.success(f"基本情報を保存しました！")
                                        time.sleep(1.5) 
                                        st.rerun()
                                        break
                                    except Exception:
                                        if attempt < max_retries_save - 1: 
                                            time.sleep(2 ** attempt)
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
                
            quiz_master = get_quiz_master_dict()
            # 💡 ① 小テストの記録を取得し、先生の関数でポイント化して合計する！
            quiz_records = get_student_quiz_records(selected_student)
            total_quiz_pts = 0
            
            for record in quiz_records:
                # 💡 3. 先生の関数に「点数」「テスト名」「満点リスト」を渡す！
                # これで、内部的に自動で正しい満点を参照して百分率を出してくれます。
                pts = calculate_quiz_points(
                    score=record["score"], 
                    quiz_name=record["quiz_name"], 
                    quiz_master_dict=quiz_master
                )
                total_quiz_pts += pts
            
            # 💡 STEP1で作った関数を呼び出して、自習ポイントを取得！
            self_study_pts = get_student_self_study_points(selected_student)
            
            # 💡 STEP2で作った計算関数に、宿題・小テスト・自習ポイントを入れて「やる気」を算出！
            current_motivation = calculate_motivation_rank(current_hw_rate, total_quiz_pts, self_study_pts)
            
            # せっかくなので、画面にも「獲得ポイント」を表示してあげましょう
            st.caption(f"🔥 獲得ポイント ｜ 小テスト: **{total_quiz_pts} pt** / 自習: **{self_study_pts} pt**")
            # 能力の計算
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
            
            # 📝 日付と種別はフォームの外に出す（種別を変えた瞬間に下の入力欄を切り替えるため）
            c1, c2 = st.columns(2)
            date = c1.date_input("実施日", datetime.date.today())
            test_type = c2.selectbox("📝 テスト種別", ["定期テスト(中間など)", "期末テスト", "外部模試", "通知表（内申点）", "その他"])

            # --- 1. 通知表（内申点）の入力 ---
            if test_type == "通知表（内申点）":
                # 🌟 st.form で囲むことで、入力のたびに再読み込みされるのを防ぎます
                with st.form("naishin_input_form"):
                    st.info("各科目の内申点（1〜5）を入力してください。")
                    n1, n2, n3, n4, n5 = st.columns(5)
                    n_eng = n1.number_input("英語 内申", 1, 5, value=None)
                    n_math = n2.number_input("数学 内申", 1, 5, value=None)
                    n_jpn = n3.number_input("国語 内申", 1, 5, value=None)
                    n_sci = n4.number_input("理科 内申", 1, 5, value=None)
                    n_soc = n5.number_input("社会 内申", 1, 5, value=None)
                    
                    st.divider()
                    nb1, nb2, nb3, nb4 = st.columns(4)
                    n_pe = nb1.number_input("保体 内申", 1, 5, value=None)
                    n_gika = nb2.number_input("技家 内申", 1, 5, value=None)
                    n_art = nb3.number_input("美術 内申", 1, 5, value=None)
                    n_mus = nb4.number_input("音楽 内申", 1, 5, value=None)
                    
                    # 🌟 st.form_submit_button に変更
                    submit_naishin = st.form_submit_button("💾 内申点を登録する", type="primary")
                    
                    if submit_naishin:
                        with st.spinner("☁️ 保存中...（混雑時は自動で再試行します）"):
                            max_retries_save = 5
                            for attempt in range(max_retries_save):
                                try:
                                    save_test_score(date, selected_student, test_type, n_eng, n_math, n_jpn, n_sci, n_soc, 
                                                    None, None, None, None, None, None, None, 
                                                    n_pe, n_gika, None, n_mus, n_art, is_naishin=True)
                                    st.cache_data.clear()
                                    st.success("内申点を登録しました！")
                                    time.sleep(1.5)
                                    st.rerun()
                                    break
                                except Exception:
                                    if attempt < max_retries_save - 1:
                                        time.sleep(2 ** attempt)
                                    else:
                                        st.error("通信エラーが発生しました。もう一度お試しください。")

            # --- 2. テスト成績（定期・期末・模試）の入力 ---
            else:
                # 🌟 こちらも st.form で囲みます
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

                    # 5教科スコア
                    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                    eng = sc1.number_input(f"英語 (/{m_eng})", 0, m_eng, value=None)
                    math_score = sc2.number_input(f"数学 (/{m_math})", 0, m_math, value=None)
                    jpn = sc3.number_input(f"国語 (/{m_jpn})", 0, m_jpn, value=None)
                    sci = sc4.number_input(f"理科 (/{m_sci})", 0, m_sci, value=None)
                    soc = sc5.number_input(f"社会 (/{m_soc})", 0, m_soc, value=None)

                    # 模試用偏差値
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

                    # 期末テスト用副教科
                    pe, tech, home, art, mus = None, None, None, None, None
                    if test_type == "期末テスト":
                        st.divider()
                        sc6, sc7, sc8, sc9, sc10 = st.columns(5)
                        pe = sc6.number_input(f"保体 (/{m_pe})", 0, m_pe, value=None)
                        tech = sc7.number_input(f"技術 (/{m_tech})", 0, m_tech, value=None)
                        home = sc8.number_input(f"家庭科 (/{m_home})", 0, m_home, value=None)
                        art = sc9.number_input(f"美術 (/{m_art})", 0, m_art, value=None)
                        mus = sc10.number_input(f"音楽 (/{m_mus})", 0, m_mus, value=None)

                    # 🌟 st.form_submit_button に変更
                    submit_test = st.form_submit_button("💾 この成績を登録する", type="primary")
                    
                    if submit_test:
                        with st.spinner("☁️ 保存中...（混雑時は自動で再試行します）"):
                            max_retries_save = 5
                            for attempt in range(max_retries_save):
                                try:
                                    save_test_score(date, selected_student, test_type, eng, math_score, jpn, sci, soc, 
                                                    dev_eng, dev_math, dev_jpn, dev_sci, dev_soc, None, None, 
                                                    pe, tech, home, mus, art, is_naishin=False)
                                    st.cache_data.clear()
                                    st.success("成績を登録しました！")
                                    time.sleep(1.5)
                                    st.rerun()
                                    break
                                except Exception:
                                    if attempt < max_retries_save - 1:
                                        time.sleep(2 ** attempt)
                                    else:
                                        st.error("通信エラーが発生しました。もう一度お試しください。")

    with tab_view:
        if not df_student_tests.empty:
            st.markdown(f"**📈 {selected_student} さんの総合点 推移**")
            if '総合' in df_student_tests.columns:
                st.line_chart(df_student_tests.set_index("テスト種別")["総合"])
            elif '5科総合' in df_student_tests.columns:
                st.line_chart(df_student_tests.set_index("テスト種別")["5科総合"])
            
            st.dataframe(df_student_tests, hide_index=True, use_container_width=True)
        else:
            st.info("まだ成績データがありません。")