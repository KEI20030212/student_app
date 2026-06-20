import streamlit as st
import datetime
import time
import re
import pandas as pd

from utils.g_sheets import (
    get_student_master,
    get_all_teacher_names,
    save_to_spreadsheet,              # 個別保存用（単発）
    save_logs_to_spreadsheet,         # 🌟 追加：一括保存用（完全バルク対応！）
    update_student_homework_rate,
    add_new_textbook,        
    get_textbook_master,
    save_quizzes_to_dedicated_sheet,  
    get_quiz_master_dict,
    get_type_advice_dict,
    save_draft_to_sheet,
    load_draft_from_sheet,
    delete_draft_from_sheet,
    get_all_logs 
)
from utils.calc_logic import (
    calculate_hw_rate, 
    calculate_quiz_points, 
    calculate_motivation_rank
)
from utils.api_guard import robust_api_call

# --- 🚀 キャッシュ関数 ---
@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_teacher_names():
    return robust_api_call(get_all_teacher_names, fallback_value=[])

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_quiz_master():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_type_advice():
    return robust_api_call(get_type_advice_dict, fallback_value={})

@st.cache_data(ttl=60, show_spinner=False)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

# 🌟 集団指導用の下書きキープレフィックス（共通項目はg_、個別項目はs_）
DRAFT_PREFIXES = (
    "num_blocks", 
    "g_date", "g_teacher", "g_slot", "g_sub", "g_num_s", 
    "g_texts", "g_new_text", "g_adv_unit", "g_adv_ranges_num", "g_adv_s", "g_adv_e",
    "g_num_q", "g_q_name", "g_q_chap", 
    "g_hw_texts", "g_new_hw_text", "g_hw_ranges_num", "g_hw_unit", "g_n_s", "g_n_e", "g_bring",
    "s_sel", "s_new", "s_att", "s_late", "s_cont", "s_hw_forgot", "s_done_start", "s_done_end", "s_d_s", "s_d_e",
    "s_hw_reason", "s_hw_fix", "s_q_score", "s_w", "s_conc", "s_reac", "s_advc", "s_pmsg", "s_next_h",
    "saved_flag", "saved_name"
)

def add_tab():
    st.session_state['num_blocks'] = st.session_state.get('num_blocks', 1) + 1

def remove_tab():
    num_blocks = st.session_state.get('num_blocks', 1)
    if num_blocks > 1:
        b_to_delete = num_blocks - 1
        for key in list(st.session_state.keys()):
            if f"_{b_to_delete}" in key:
                del st.session_state[key]
        st.session_state['num_blocks'] = num_blocks - 1

def render_group_input_page():
    user_id = st.session_state.get('user_id', st.session_state.get('username', 'default_user'))

    with st.sidebar:
        st.header("☁️ クラウド下書き保存")
        st.caption("サーバーがスリープしても、データは守られます！")
        
        last_saved_time = st.session_state.get('last_saved_time', None)
        if last_saved_time:
            st.success(f"🕒 最終保存: {last_saved_time}")
        else:
            st.caption("最終保存日時: 未取得（またはデータなし）")
            
        c1, c2 = st.columns(2)
        if c1.button("☁️ 保存", use_container_width=True):
            draft = {k: v for k, v in st.session_state.items() if any(k.startswith(p) for p in DRAFT_PREFIXES)}
            if not draft or len(draft) < 3:
                st.error("⚠️ 保存するデータがありません。")
            else:
                with st.spinner("クラウドへ保存中..."):
                    success, saved_time = robust_api_call(save_draft_to_sheet, username=user_id, draft_data=draft, fallback_value=(False, None))
                    if success:
                        st.session_state['last_saved_time'] = saved_time
                        st.success("✅ クラウド保存完了！")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error("保存失敗")
            
        if c2.button("📂 復元", use_container_width=True):
            with st.spinner("クラウドから復元中..."):
                draft, saved_time = robust_api_call(load_draft_from_sheet, username=user_id, fallback_value=(None, None))
                if draft:
                    for k, v in draft.items(): st.session_state[k] = v
                    st.session_state['last_saved_time'] = saved_time
                    st.success("✅ 復元しました！")
                    time.sleep(1.5)
                    st.rerun() 
                else: st.warning("保存データがありません")
                    
        if st.button("🗑️ 保存データを削除", use_container_width=True):
            with st.spinner("削除中..."):
                success = robust_api_call(delete_draft_from_sheet, username=user_id, fallback_value=False)
                if success:
                    st.session_state['last_saved_time'] = None
                    st.success("✅ 削除しました！")
                    time.sleep(1.5)
                    st.rerun()
                else: st.error("削除失敗")
        st.divider()
        st.warning("🚨 **入力途中で離席する際は必ず「☁️ 保存」を押してください！**")

    if last_saved_time:
        st.error("⚠️ **前回中断した入力データがクラウドに残っています！** 続きから入力する場合は「📂 復元」を押してください。")

    student_df = cached_get_student_master()
    student_options = (student_df['生徒ID'].astype(str) + " - " + student_df['生徒名']).tolist() if not student_df.empty else []
    teacher_names = cached_get_teacher_names()
    text_options = list(cached_get_textbook_master().keys())
    
    quiz_details = cached_get_quiz_master()
    quiz_names = list(set([k.split("_", 1)[0] for k in quiz_details.keys() if "_" in k])) or ["設定なし"]

    df_all_logs = cached_get_all_logs()

    st.write("### 🗂️ 授業コマの管理")
    num_blocks = st.session_state.get('num_blocks', 1)

    col_add, col_del, _ = st.columns([2, 2, 6])
    with col_add: st.button("➕ 新しいクラスを追加", use_container_width=True, on_click=add_tab)
    with col_del:
        if num_blocks > 1: st.button("➖ 最後のクラスを削除", use_container_width=True, on_click=remove_tab)

    tabs = st.tabs([f"🏫 クラス {b+1}" for b in range(num_blocks)])
    single_save_triggered = None
    all_save_triggered = None

    for b in range(num_blocks):
        with tabs[b]:
            st.markdown("#### 🌟 1. クラスの基本情報（共通設定）")
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])
                date = c1.date_input("授業日", datetime.date.today(), key=f"g_date_{b}")
                teacher_name = c2.selectbox("👨‍🏫 担当講師", teacher_names, index=None, placeholder="講師を選択", key=f"g_teacher_{b}")
                
                time_slots = ["Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)", "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)", "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"]
                class_slot = c3.selectbox("⏰ 授業コマ", time_slots, index=None, placeholder="コマを選択", key=f"g_slot_{b}")
                subject = c4.selectbox("📚 科目", ["英語", "数学", "国語", "理科", "社会"], index=None, placeholder="科目を選択", key=f"g_sub_{b}")
                num_students = c5.number_input("👥 生徒数", min_value=1, max_value=30, value=5, key=f"g_num_s_{b}")

            if not teacher_name or not class_slot or not subject:
                st.info("👆 講師、コマ、科目を選択すると、授業内容の設定が開きます。")
                continue 

            # ---------------------------------------------------------
            # 🌟 共通設定（テキスト・進捗・宿題・小テスト）
            # ---------------------------------------------------------
            st.markdown("#### 🌟 2. 授業内容 ＆ 宿題（全員共通）")
            filtered_text_options = [t for t in text_options if "Myeトレ" not in t or subject in t]
            
            with st.container(border=True):
                st.write("📚 **本日の授業進捗**")
                g_selected_texts = st.multiselect("使用テキスト (複数可)", ["🆕 新規テキスト入力"] + filtered_text_options, key=f"g_texts_{b}")
                
                if "🆕 新規テキスト入力" in g_selected_texts:
                    new_text = st.text_input("📝 新しいテキスト名", key=f"g_new_text_{b}")
                    if new_text:
                        robust_api_call(add_new_textbook, new_text)
                        g_selected_texts.remove("🆕 新規テキスト入力")
                        if new_text not in g_selected_texts: g_selected_texts.append(new_text)
                        cached_get_textbook_master.clear()

                g_advanced_p_list = []
                if g_selected_texts and "🆕 新規テキスト入力" not in g_selected_texts:
                    g_text_name_str = "、".join(g_selected_texts)
                    for t_idx, t_name in enumerate(g_selected_texts):
                        st.caption(f"📘 {t_name} の進捗")
                        if "Myeトレ" in t_name:
                            units_raw = cached_get_textbook_master().get(t_name, {})
                            if isinstance(units_raw, dict): u_opts = [str(v).strip() if str(v).strip() else str(k).strip() for k, v in units_raw.items()]
                            elif isinstance(units_raw, str): u_opts = [u.strip() for u in units_raw.replace('、', ',').split(',') if u.strip()]
                            elif isinstance(units_raw, list): u_opts = [str(u).strip() for u in units_raw if str(u).strip() != ""]
                            else: u_opts = []
                            adv_u = st.selectbox("単元を選択", [""] + u_opts, key=f"g_adv_unit_{b}_{t_idx}")
                            g_advanced_p_list.append(f"{t_name}: {adv_u}" if adv_u else f"{t_name}: -")
                        else:
                            adv_r_num = st.number_input("進捗の範囲数", min_value=1, max_value=5, value=1, key=f"g_adv_ranges_num_{b}_{t_idx}")
                            valid = False
                            for r_idx in range(adv_r_num):
                                c_s, c_e = st.columns(2)
                                a_s = c_s.number_input(f"開始P ({r_idx+1})", min_value=0, value=0, key=f"g_adv_s_{b}_{t_idx}_{r_idx}")
                                a_e = c_e.number_input(f"終了P ({r_idx+1})", min_value=0, value=0, key=f"g_adv_e_{b}_{t_idx}_{r_idx}")
                                if a_e >= a_s and a_e > 0:
                                    g_advanced_p_list.append(f"{t_name}: P.{a_s}〜{a_e}")
                                    valid = True
                            if not valid: g_advanced_p_list.append(f"{t_name}: -")
                    g_advanced_p_str = "\n".join(g_advanced_p_list)
                else:
                    g_text_name_str = "-"
                    g_advanced_p_str = "-"
                
                st.divider()
                st.write("💯 **実施する小テストの設定**")
                g_num_quizzes = st.number_input("小テスト実施回数", min_value=0, max_value=5, value=0, step=1, key=f"g_num_q_{b}")
                g_quizzes_setup = []
                for q_idx in range(g_num_quizzes):
                    c_q1, c_q2 = st.columns(2)
                    q_n = c_q1.selectbox(f"テスト名 ({q_idx+1})", quiz_names, index=None, key=f"g_q_name_{b}_{q_idx}")
                    q_c = c_q2.number_input(f"単元/回 ({q_idx+1})", min_value=1, value=1, key=f"g_q_chap_{b}_{q_idx}")
                    max_pts = 100
                    if q_n:
                        matched = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_n}_")]
                        if matched: max_pts = int(pd.Series(matched).mode()[0])
                    if q_n: g_quizzes_setup.append({"name": q_n, "chap": q_c, "max": max_pts})

                st.divider()
                st.write("🚀 **次回の宿題指示**")
                g_hw_texts = st.multiselect("次回の宿題テキスト (複数可)", filtered_text_options, key=f"g_hw_texts_{b}")
                g_hw_pages_list = []
                if g_hw_texts:
                    for t_idx, h_name in enumerate(g_hw_texts):
                        st.caption(f"📘 {h_name} の宿題")
                        if "Myeトレ" in h_name:
                            units_raw = cached_get_textbook_master().get(h_name, {})
                            u_opts = [str(v).strip() if str(v).strip() else str(k).strip() for k, v in units_raw.items()] if isinstance(units_raw, dict) else []
                            hw_u = st.multiselect("単元", u_opts, key=f"g_hw_unit_{b}_{t_idx}")
                            if hw_u: g_hw_pages_list.append(f"{h_name}: {', '.join(hw_u)}")
                        else:
                            hw_r_num = st.number_input("範囲数", min_value=1, max_value=5, value=1, key=f"g_hw_ranges_num_{b}_{t_idx}")
                            for r_idx in range(hw_r_num):
                                c_s, c_e = st.columns(2)
                                h_s = c_s.number_input(f"開始P ({r_idx+1})", min_value=0, value=0, key=f"g_n_s_{b}_{t_idx}_{r_idx}")
                                h_e = c_e.number_input(f"終了P ({r_idx+1})", min_value=0, value=0, key=f"g_n_e_{b}_{t_idx}_{r_idx}")
                                if h_e >= h_s and h_e > 0: g_hw_pages_list.append(f"{h_name}: P.{h_s}〜{h_e}")
                    g_hw_pages_str = "\n".join(g_hw_pages_list) if g_hw_pages_list else "-"
                    g_hw_text_str = "、".join(g_hw_texts)
                else:
                    g_hw_text_str = "-"
                    g_hw_pages_str = "-"
                
                g_bring = st.text_input("🎒 次回の持ち物", key=f"g_bring_{b}", placeholder="例: ノート")

            # ---------------------------------------------------------
            # 🌟 個別設定（生徒ごとの差異を入力）
            # ---------------------------------------------------------
            st.markdown("#### 🌟 3. 生徒ごとの記録（個別入力）")
            input_data_list = []

            for i in range(num_students):
                is_saved = st.session_state.get(f"saved_flag_{b}_{i}", False)
                saved_name = st.session_state.get(f"saved_name_{b}_{i}", f"生徒{i+1}")

                with st.expander(f"👤 {saved_name}" + (" ［✅ 保存済］" if is_saved else ""), expanded=not is_saved):
                    if is_saved:
                        st.success(f"保存済みです。修正は「授業記録の修正」から行ってください。")
                        continue

                    sel_student = st.selectbox("生徒名", ["🆕 新規登録（通常）", "🔰 新規登録（体験）"] + student_options, index=None, key=f"s_sel_{b}_{i}")
                    student_id, name, is_trial = None, None, False

                    if sel_student == "🆕 新規登録（通常）":
                        name = st.text_input("新しい生徒名", key=f"s_new_{b}_{i}")
                        student_id = "NEW"
                    elif sel_student == "🔰 新規登録（体験）":
                        name = st.text_input("体験生徒名", key=f"s_new_{b}_{i}")
                        student_id, is_trial = "TRIAL", True
                    elif sel_student:
                        student_id, name = sel_student.split(" - ")[0], sel_student.split(" - ")[1]

                    if not name:
                        st.info("生徒を選択してください。")
                        continue

                    # アドバイス表示
                    type_advice_dict = cached_get_type_advice()
                    student_type_str = ""
                    if not student_df.empty and 'タイプ' in student_df.columns:
                        row = student_df[student_df['生徒名'] == name]
                        if not row.empty: student_type_str = str(row.iloc[0].get('タイプ', ''))
                    if student_type_str and student_type_str.lower() != "nan":
                        advices = [f"・{t_adv}" for t_key, t_adv in type_advice_dict.items() if t_key in student_type_str]
                        if advices: st.info("💡 **指導アドバイス**\n" + "\n".join(advices))

                    c_att1, c_att2 = st.columns(2)
                    attendance = c_att1.selectbox("📅 出欠状況", ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"], key=f"s_att_{b}_{i}")
                    late_time = c_att2.number_input("⏰ 遅刻 (分)", min_value=0, step=5, key=f"s_late_{b}_{i}")

                    if "欠席" in attendance:
                        st.warning("欠席のため以降の入力はスキップされます。")
                        input_data_list.append({
                            "original_idx": i, "student_id": student_id, "name": name, "subject": subject, 
                            "text_name": g_text_name_str, "advanced_p": g_advanced_p_str, "quiz_records": [], "w_nums_for_sheet": "", 
                            "attendance": attendance, "late_time": late_time, "concentration": "-", "reaction": "-",
                            "advice": "-", "parent_msg": "-", "next_handover": "-", "assigned_p": 0, "completed_p": 0, 
                            "motivation_rank": 0, "next_hw_text": g_hw_text_str, "next_hw_pages": g_hw_pages_str, 
                            "is_trial": is_trial, "hw_reason": "", "hw_fix": "", "next_bring": g_bring
                        })
                        continue

                    st.write("---")
                    
                    # 宿題達成状況
                    assigned_p, completed_p = 0, 0
                    if is_trial:
                        hw_reason_val, hw_fix_val = "", ""
                    else:
                        st.markdown("**📝 今回の宿題達成状況**")
                        
                        # 自動計算のために前回ログを取得
                        last_hw_pages = "なし"
                        if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns:
                            name_col = '生徒名' if '生徒名' in df_all_logs.columns else '名前'
                            df_s = df_all_logs[(df_all_logs[name_col] == name) & (df_all_logs['科目'] == subject)].copy()
                            if not df_s.empty:
                                df_s['日時'] = pd.to_datetime(df_s['日時'], format='mixed', errors='coerce')
                                last_row = df_s.sort_values('日時', ascending=False).iloc[0]
                                last_hw_pages = str(last_row.get('次回の宿題ページ数', ''))

                        assigned_hw_list = []
                        if str(last_hw_pages).strip() and str(last_hw_pages).strip() not in ["-", "なし", "nan"]:
                            for line in str(last_hw_pages).split('\n'):
                                match = re.search(r'(?:(.*?)[:：]\s*)?[P\.]*(\d+)\s*[〜~-]\s*(\d+)', line)
                                if match:
                                    a_start, a_end = int(match.group(2)), int(match.group(3))
                                    if a_end >= a_start:
                                        pages = a_end - a_start + 1
                                        assigned_p += pages
                                        assigned_hw_list.append({"start": a_start, "end": a_end, "pages": pages})

                        c_hk1, c_hk2 = st.columns(2)
                        is_continuous = c_hk1.checkbox("🔄 前回を引き継ぐ", key=f"s_cont_{b}_{i}")
                        is_hw_forgotten = c_hk2.checkbox("❌ 忘れた・やってない", key=f"s_hw_forgot_{b}_{i}")

                        if is_continuous:
                            assigned_p = 0
                        elif is_hw_forgotten:
                            completed_p = 0
                        else:
                            if not assigned_hw_list:
                                st.caption("※手動入力欄")
                                cd1, cd2 = st.columns(2)
                                d_s = cd1.number_input("やった開始P", min_value=0, key=f"s_done_start_{b}_{i}")
                                d_e = cd2.number_input("やった終了P", min_value=0, key=f"s_done_end_{b}_{i}")
                                if d_e >= d_s and d_e > 0: completed_p = d_e - d_s + 1
                            else:
                                for h_idx, hw in enumerate(assigned_hw_list):
                                    st.caption(f"指示: P.{hw['start']}〜{hw['end']}")
                                    cd1, cd2 = st.columns(2)
                                    d_s = cd1.number_input("やった開始P", value=hw['start'], min_value=0, key=f"s_d_s_{b}_{i}_{h_idx}")
                                    d_e = cd2.number_input("やった終了P", value=hw['end'], min_value=0, key=f"s_d_e_{b}_{i}_{h_idx}")
                                    if d_e >= d_s and d_e > 0: completed_p += (d_e - d_s + 1)
                            st.caption(f"📊 出した宿題: {assigned_p} P / やった宿題: {completed_p} P")

                        hw_reason_val, hw_fix_val = "", ""
                        if (assigned_p > 0 and completed_p < assigned_p) or is_hw_forgotten:
                            cr1, cr2 = st.columns(2)
                            reason_sel = cr1.selectbox("未達成理由", ["", "難易度", "文量", "時間管理", "事故", "その他"], key=f"s_hw_reason_{b}_{i}")
                            hw_reason_val = reason_sel
                            fix_sel = cr2.selectbox("修正策", ["", "文量調整", "期限延長", "内容変更", "再約束", "その他"], key=f"s_hw_fix_{b}_{i}")
                            hw_fix_val = fix_sel

                    # 小テスト
                    quiz_records = []
                    w_nums_for_sheet_list = []
                    current_quiz_pts = 0
                    if g_quizzes_setup:
                        st.markdown("**💯 小テスト結果**")
                        for q_idx, q in enumerate(g_quizzes_setup):
                            cq1, cq2 = st.columns(2)
                            sc = cq1.number_input(f"【{q['name']}】点数 (/{q['max']}点)", min_value=0, max_value=q['max'], value=q['max'], key=f"s_q_score_{b}_{i}_{q_idx}")
                            w = cq2.text_input("ミス問題番号", key=f"s_w_{b}_{i}_{q_idx}")
                            quiz_records.append({"quiz_name": q['name'], "unit": q['chap'], "score": sc})
                            if w: w_nums_for_sheet_list.append(w)
                            current_quiz_pts += calculate_quiz_points(sc, q['name'], quiz_details)
                    w_nums_for_sheet = ",".join(w_nums_for_sheet_list)
                    
                    today_hw_rate = calculate_hw_rate(assigned_p, completed_p)
                    motivation_rank = calculate_motivation_rank(today_hw_rate, current_quiz_pts, 0)

                    # 様子＆コメント
                    st.write("---")
                    cc1, cc2 = st.columns(2)
                    conc = cc1.selectbox("集中力", ["超集中", "前向き", "疲労気味", "ムラあり", "集中できない"], index=None, key=f"s_conc_{b}_{i}")
                    reac = cc2.selectbox("ミスへの反応", ["原因を分析した", "悔しがった", "放置しようとした"], index=None, key=f"s_reac_{b}_{i}")

                    advc = st.text_area("🌟 褒めた点など", height=60, key=f"s_advc_{b}_{i}")
                    pmsg = st.text_area("👪 保護者への連絡", height=60, key=f"s_pmsg_{b}_{i}")
                    nh = st.text_area("🔄 次回への引継ぎ事項", height=60, key=f"s_next_h_{b}_{i}")

                    # 個別保存データ組み立て
                    input_data_list.append({
                        "original_idx": i, "student_id": student_id, "name": name, "subject": subject, 
                        "text_name": g_text_name_str, "advanced_p": g_advanced_p_str, "quiz_records": quiz_records, 
                        "w_nums_for_sheet": w_nums_for_sheet, "attendance": attendance, "late_time": late_time, 
                        "concentration": conc or "-", "reaction": reac or "-", "advice": advc, "parent_msg": pmsg, 
                        "next_handover": nh, "assigned_p": assigned_p, "completed_p": completed_p, 
                        "motivation_rank": motivation_rank, "next_hw_text": g_hw_text_str, "next_hw_pages": g_hw_pages_str, 
                        "is_trial": is_trial, "hw_reason": hw_reason_val, "hw_fix": hw_fix_val, "next_bring": g_bring
                    })

                    # ==========================================
                    # 👤 【個別保存】の処理（単発）
                    # ==========================================
                    if st.button(f"👤 {name} を個別に保存", key=f"save_s_{b}_{i}", use_container_width=True):
                        with st.status(f"{name} を保存中...", expanded=True) as status:
                            actual_class_type = f"集団({num_students}名)"
                            
                            success = robust_api_call(
                                save_to_spreadsheet, student_id=student_id, name=name, subject=subject, text_name=g_text_name_str,
                                advanced_p=g_advanced_p_str, quiz_records=[], date=date, teacher_name=teacher_name, class_type=actual_class_type,
                                class_slot=class_slot, advice=advc, parent_msg=pmsg, next_handover=nh, assigned_p=assigned_p, 
                                completed_p=completed_p, motivation_rank=motivation_rank, next_hw_text=g_hw_text_str,
                                next_hw_pages=g_hw_pages_str, late_time=late_time, concentration=conc or "-", reaction=reac or "-",
                                attendance=attendance, hw_reason=hw_reason_val, hw_fix=hw_fix_val, next_bring=g_bring, fallback_value=False
                            )
                            if success:
                                # 小テストのバルク送信（1人分だけでも配列に入れてバルク関数を使う）
                                if quiz_records:
                                    single_quiz_rows = []
                                    for q in quiz_records:
                                        single_quiz_rows.append([
                                            date.strftime("%Y/%m/%d"), name, q["quiz_name"], q["unit"], q["score"], "", "授業内"
                                        ])
                                    robust_api_call(save_quizzes_to_dedicated_sheet, single_quiz_rows)
                                    
                                if attendance != "欠席（振替なし）" and "欠席" not in attendance and not is_trial:
                                    try: 
                                        robust_api_call(update_student_homework_rate, name, subject, assigned_p, completed_p)
                                    except: pass 
                                status.update(label="保存完了", state="complete", expanded=False)
                                st.session_state[f"saved_flag_{b}_{i}"] = True
                                st.session_state[f"saved_name_{b}_{i}"] = name
                                single_save_triggered = True
                            else:
                                status.update(label="保存失敗", state="error")
                                st.error("保存失敗")

            st.divider()
            
            # ==========================================
            # 🚀 【全員まとめて保存】完全バルク対応版
            # ==========================================
            if len(input_data_list) > 0:
                actual_attendees = sum(1 for data in input_data_list if "欠席" not in data["attendance"])
                actual_class_type = f"集団({actual_attendees}名)"
                btn_label = f"🚀 クラス {b+1} の全員をまとめて保存する" if len(input_data_list) == num_students else f"🚀 未保存の {len(input_data_list)}名 をまとめて保存"

                if st.button(btn_label, type="primary", key=f"save_all_{b}", use_container_width=True):
                    with st.status("データを保存中...", expanded=True) as status:
                        
                        # 🌟 メインログ用と小テスト用の「超巨大な箱」を用意
                        all_main_log_rows = []
                        all_class_quiz_rows = []
                        
                        date_str = date.strftime("%Y/%m/%d") if hasattr(date, 'strftime') else str(date)
                        
                        for data in input_data_list:
                            o_idx = data["original_idx"]
                            
                            # 欠席者や保存済みの人はスキップ
                            if "欠席" in data.get("attendance", "") or st.session_state.get(f"saved_flag_{b}_{o_idx}", False):
                                st.session_state[f"saved_flag_{b}_{o_idx}"] = True
                                st.session_state[f"saved_att_{b}_{o_idx}"] = data.get("attendance", "")
                                continue

                            # 🌟 メインログデータを24列のリストに梱包して箱に入れる
                            all_main_log_rows.append([
                                date_str, 
                                data.get("student_id", ""), 
                                data.get("name", ""), 
                                data.get("subject", ""), 
                                data.get("text_name", ""), 
                                data.get("advanced_p", ""), 
                                teacher_name, 
                                actual_class_type,
                                data.get("attendance", ""), 
                                class_slot, 
                                data.get("advice", "-"), 
                                data.get("parent_msg", "-"), 
                                data.get("next_handover", "-"), 
                                data.get("assigned_p", 0), 
                                data.get("completed_p", 0), 
                                data.get("motivation_rank", 0), 
                                data.get("hw_reason", ""),
                                data.get("hw_fix", ""),
                                data.get("next_hw_text", "-"),
                                data.get("next_hw_pages", ""), 
                                data.get("late_time", 0),        
                                data.get("concentration", "-"), 
                                data.get("reaction", "-"),
                                data.get("next_bring", "")
                            ])

                            # 🌟 小テストデータも箱に入れる
                            if data.get("quiz_records") and len(data["quiz_records"]) > 0:
                                for q in data["quiz_records"]:
                                    all_class_quiz_rows.append([
                                        date_str,
                                        data["name"],
                                        q["quiz_name"],
                                        q["unit"],
                                        q["score"],
                                        "",
                                        "授業内"
                                    ])
                                    
                            # （※宿題達成率の更新は個別APIなのでここで回す）
                            if data["attendance"] != "欠席（振替なし）" and "欠席" not in data["attendance"] and not data.get("is_trial"):
                                try:
                                    robust_api_call(update_student_homework_rate, data["name"], data["subject"], data["assigned_p"], data["completed_p"])
                                except Exception:
                                    pass 
                                    
                            st.session_state[f"saved_flag_{b}_{o_idx}"] = True
                            st.session_state[f"saved_name_{b}_{o_idx}"] = data["name"]
                            st.session_state[f"saved_att_{b}_{o_idx}"] = data.get("attendance", "")

                        # ==========================================
                        # 📦 箱に溜まったデータを、それぞれ一発でGoogleに納品！
                        # ==========================================
                        all_success = True
                        
                        if all_main_log_rows:
                            status.write("📝 全員のメイン記録を一括送信中...")
                            success = robust_api_call(save_logs_to_spreadsheet, all_main_log_rows)
                            if not success:
                                all_success = False
                                
                        if all_success and all_class_quiz_rows:
                            status.write("💯 全員の小テスト記録を一括送信中...")
                            success_q = robust_api_call(save_quizzes_to_dedicated_sheet, all_class_quiz_rows)
                            if not success_q:
                                all_success = False

                        if all_success:
                            status.update(label="保存完了！", state="complete", expanded=False)
                            st.success(f"✅ クラス {b+1}（{actual_attendees}名）の記録を保存しました！")
                            st.session_state['last_saved_time'] = None 
                            all_save_triggered = (b, num_students)
                        else:
                            status.update(label="一部の保存に失敗しました", state="error", expanded=True)
                            st.error("🚨 通信エラーが発生しました。時間を置いてからやり直してください。")

            if sum(1 for idx in range(num_students) if st.session_state.get(f"saved_flag_{b}_{idx}", False)) == num_students and not all_save_triggered:
                st.success("🎉 このクラス全員の入力が完了しました！画面をリセットします...")
                all_save_triggered = (b, num_students)

    # 保存完了時の画面リセット＆キャッシュ消去
    if all_save_triggered:
        b_idx, students_count = all_save_triggered
        for k in ["g_date", "g_teacher", "g_slot", "g_sub", "g_num_s", "g_texts", "g_new_text", "g_num_q", "g_hw_texts", "g_new_hw_text", "g_bring"]:
            if f"{k}_{b_idx}" in st.session_state: del st.session_state[f"{k}_{b_idx}"]
        
        target_prefixes = ["g_adv_s", "g_adv_e", "g_adv_unit", "g_adv_ranges_num", "g_q_name", "g_q_chap", "g_n_s", "g_n_e", "g_hw_unit", "g_hw_ranges_num", "s_sel", "s_new", "s_att", "s_late", "s_cont", "s_hw_forgot", "s_done_start", "s_done_end", "s_d_s", "s_d_e", "s_hw_reason", "s_hw_fix", "s_q_score", "s_w", "s_conc", "s_reac", "s_advc", "s_pmsg", "s_next_h", "saved_flag", "saved_name"]
        
        for key in list(st.session_state.keys()):
            for p in target_prefixes:
                if key.startswith(f"{p}_{b_idx}_"):
                    del st.session_state[key]
                    break
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()

    elif single_save_triggered:
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()