import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import update_test_score_data
from utils.api_guard import robust_api_call

def render_test_score_edit(selected_student, df_student_tests):
    """テスト・内申点の修正フォーム部分"""
    if df_student_tests.empty or 'APIエラー発生' in df_student_tests.columns:
        st.info("修正できる成績データがありません。先に「テスト成績を入力」から登録してください。")
        return

    with st.container(border=True):
        st.write(f"**{selected_student}** さんの登録済みデータを修正します。")
        
        # 探しやすいように日時が新しい順に並べる
        df_edit = df_student_tests.copy()
        df_edit['日時_dt'] = pd.to_datetime(df_edit['日時'], errors='coerce')
        df_edit = df_edit.sort_values('日時_dt', ascending=False)
        
        options = ["選択してください"]
        idx_mapping = {}
        for idx, row in df_edit.iterrows():
            date_str = row['日時_dt'].strftime('%Y/%m/%d') if pd.notna(row['日時_dt']) else str(row.get('日時', ''))
            t_type = row.get('テスト種別', '不明')
            # どの行を修正するか特定するための秘密のIDを持たせる
            opt_key = f"{date_str} - {t_type} (内部ID:{idx})"
            options.append(opt_key)
            idx_mapping[opt_key] = idx
            
        selected_option = st.selectbox("🛠️ 修正するデータを選択", options)
        
        if selected_option != "選択してください":
            sel_idx = idx_mapping[selected_option]
            target_row = df_edit.loc[sel_idx]
            # Pandasは0始まり、スプレッドシートは1始まりでヘッダーが1行あるため「+2」が実際の行番号
            sheet_row_idx = sel_idx + 2 
            
            st.divider()
            
            # 既存のデータを安全に取り出すための魔法の関数群
            def get_val(col, type_func=int):
                v = target_row.get(col)
                if pd.isna(v) or str(v).strip() in ["", "-"]: return None
                try: return type_func(v)
                except: return None
                    
            def get_str(col):
                v = target_row.get(col)
                if pd.isna(v) or str(v).strip() == "-": return ""
                return str(v).strip()
                
            def get_att_idx(val):
                opts = ["", "A", "B", "C"]
                return opts.index(val) if val in opts else 0

            test_type = get_str('テスト種別') or '定期テスト(中間など)'
            default_date = target_row['日時_dt'].date() if pd.notna(target_row['日時_dt']) else datetime.date.today()
            
            c1, c2 = st.columns(2)
            edit_date = c1.date_input("実施日を修正", default_date)
            st.info(f"現在のテスト種別: **{test_type}** （※データ混同を防ぐため、種別自体は変更できません）")

            # ▼ 内申点フォーム
            if test_type == "通知表（内申点）":
                with st.form("naishin_edit_form"):
                    n1, n2, n3, n4, n5 = st.columns(5)
                    n_eng = n1.number_input("英語 内申", 1, 5, value=get_val("英語 内申"))
                    att_eng = n1.selectbox("英語 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("英語 態度")))
                    
                    n_math = n2.number_input("数学 内申", 1, 5, value=get_val("数学 内申"))
                    att_math = n2.selectbox("数学 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("数学 態度")))
                    
                    n_jpn = n3.number_input("国語 内申", 1, 5, value=get_val("国語 内申"))
                    att_jpn = n3.selectbox("国語 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("国語 態度")))
                    
                    n_sci = n4.number_input("理科 内申", 1, 5, value=get_val("理科 内申"))
                    att_sci = n4.selectbox("理科 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("理科 態度")))
                    
                    n_soc = n5.number_input("社会 内申", 1, 5, value=get_val("社会 内申"))
                    att_soc = n5.selectbox("社会 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("社会 態度")))
                    
                    st.divider()
                    nb1, nb2, nb3, nb4 = st.columns(4)
                    
                    n_pe = nb1.number_input("保体 内申", 1, 5, value=get_val("保体 内申"))
                    att_pe = nb1.selectbox("保体 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("保体 態度")))
                    
                    n_gika = nb2.number_input("技家 内申", 1, 5, value=get_val("技家 内申"))
                    att_gika = nb2.selectbox("技家 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("技家 態度")))
                    
                    n_art = nb3.number_input("美術 内申", 1, 5, value=get_val("美術 内申"))
                    att_art = nb3.selectbox("美術 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("美術 態度")))
                    
                    n_mus = nb4.number_input("音楽 内申", 1, 5, value=get_val("音楽 内申"))
                    att_mus = nb4.selectbox("音楽 態度", ["", "A", "B", "C"], index=get_att_idx(get_str("音楽 態度")))
                    
                    submit_edit = st.form_submit_button("💾 修正を上書き保存する", type="primary")
                    
                    if submit_edit:
                        with st.spinner("☁️ 保存中..."):
                            def _update_naishin():
                                update_test_score_data(sheet_row_idx, edit_date, selected_student, test_type,
                                    n_eng, n_math, n_jpn, n_sci, n_soc, 
                                    None, None, None, None, None, 
                                    n_pe, n_gika, None, n_mus, n_art, is_naishin=True,
                                    att_eng=att_eng, att_math=att_math, att_jpn=att_jpn, 
                                    att_sci=att_sci, att_soc=att_soc, att_pe=att_pe, 
                                    att_gika=att_gika, att_art=att_art, att_mus=att_mus)
                                return True
                            
                            success = robust_api_call(_update_naishin, fallback_value=False)
                            if success:
                                st.cache_data.clear()
                                st.success("内申点の修正を保存しました！")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("通信エラーが発生しました。")

            # ▼ 通常テストフォーム
            else:
                with st.form("test_score_edit_form"):
                    st.markdown("##### 📊 点数の修正")
                    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                    eng = sc1.number_input("英語", 0, 100, value=get_val("英語"))
                    math_score = sc2.number_input("数学", 0, 100, value=get_val("数学"))
                    jpn = sc3.number_input("国語", 0, 100, value=get_val("国語"))
                    sci = sc4.number_input("理科", 0, 100, value=get_val("理科"))
                    soc = sc5.number_input("社会", 0, 100, value=get_val("社会"))

                    dev_eng, dev_math, dev_jpn, dev_sci, dev_soc = None, None, None, None, None
                    if test_type == "外部模試":
                        st.divider()
                        st.markdown("##### 📊 偏差値の修正")
                        d1, d2, d3, d4, d5 = st.columns(5)
                        dev_eng = d1.number_input("英語 偏差値", 0.0, 90.0, value=get_val("英語 偏差値", float), step=0.1)
                        dev_math = d2.number_input("数学 偏差値", 0.0, 90.0, value=get_val("数学 偏差値", float), step=0.1)
                        dev_jpn = d3.number_input("国語 偏差値", 0.0, 90.0, value=get_val("国語 偏差値", float), step=0.1)
                        dev_sci = d4.number_input("理科 偏差値", 0.0, 90.0, value=get_val("理科 偏差値", float), step=0.1)
                        dev_soc = d5.number_input("社会 偏差値", 0.0, 90.0, value=get_val("社会 偏差値", float), step=0.1)

                    pe, tech, home, art, mus = None, None, None, None, None
                    if test_type == "期末テスト":
                        st.divider()
                        st.markdown("##### 📊 副教科の点数修正")
                        sc6, sc7, sc8, sc9, sc10 = st.columns(5)
                        pe = sc6.number_input("保体", 0, 100, value=get_val("保体"))
                        tech = sc7.number_input("技術", 0, 100, value=get_val("技術"))
                        home = sc8.number_input("家庭科", 0, 100, value=get_val("家庭"))
                        art = sc9.number_input("美術", 0, 100, value=get_val("美術"))
                        mus = sc10.number_input("音楽", 0, 100, value=get_val("音楽"))

                    submit_edit = st.form_submit_button("💾 修正を上書き保存する", type="primary")
                    
                    if submit_edit:
                        with st.spinner("☁️ 保存中..."):
                            def _update_test():
                                update_test_score_data(sheet_row_idx, edit_date, selected_student, test_type,
                                    eng, math_score, jpn, sci, soc, 
                                    dev_eng, dev_math, dev_jpn, dev_sci, dev_soc, 
                                    pe, tech, home, mus, art, is_naishin=False)
                                return True
                            
                            success = robust_api_call(_update_test, fallback_value=False)
                            if success:
                                st.cache_data.clear()
                                st.success("成績の修正を保存しました！")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("通信エラーが発生しました。")