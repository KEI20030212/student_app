import streamlit as st
import datetime
import time
from utils.g_sheets import save_test_score
from utils.api_guard import robust_api_call

def render_test_score_input(selected_student):
    """テスト・内申点の入力フォーム部分"""
    with st.container(border=True):
        st.write(f"**{selected_student}** さんのテスト結果・内申点を入力します。")
        
        c1, c2 = st.columns(2)
        test_date = c1.date_input("実施日", datetime.date.today())
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
                            save_test_score(test_date, selected_student, test_type, n_eng, n_math, n_jpn, n_sci, n_soc, 
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
                            save_test_score(test_date, selected_student, test_type, eng, math_score, jpn, sci, soc, 
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