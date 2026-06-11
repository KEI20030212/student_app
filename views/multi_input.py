import streamlit as st
import datetime
import time
import re
import pandas as pd

from utils.g_sheets import (
    get_student_master,
    get_all_teacher_names,
    save_to_spreadsheet, 
    update_student_homework_rate,
    add_new_textbook,        
    get_textbook_master,
    save_quiz_to_dedicated_sheet,
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

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
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

DRAFT_PREFIXES = (
    "num_blocks", "class_date", "class_type", 
    "sb_", "sel_student", "new_name", "att", "late", "sub", "texts", "new_usage_text", 
    "adv_start", "adv_end", "adv_unit", "num_q", "q_name", "q_chap", "q_score", "w",
    "cont", "hw_forgot", "done_start", "done_end", "conc", "reac", "hw_texts", "new_hw_text", 
    "n_start", "n_end", "hw_unit", "advc", "p_msg", "next_h", "d_s", "d_e", "n_s", "n_e", "hw_ranges_num",
    "hw_reason", "hw_fix", "bring"
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

def render_multi_input_page():
    user_id = st.session_state.get('user_id', st.session_state.get('username', 'default_user'))

    with st.sidebar:
        st.header("☁️ クラウド下書き保存")
        st.caption("サーバーがスリープしても、データはスプレッドシートに守られます！")
        
        last_saved_time = st.session_state.get('last_saved_time', None)
        if last_saved_time:
            st.success(f"🕒 最終保存: {last_saved_time}")
        else:
            st.caption("最終保存日時: 未取得（またはデータなし）")
            
        c1, c2 = st.columns(2)
        if c1.button("☁️ 保存", use_container_width=True):
            draft = {}
            for k, v in st.session_state.items():
                if any(k.startswith(p) for p in DRAFT_PREFIXES):
                    draft[k] = v
            
            if not draft or len(draft) < 3:
                st.error("⚠️ 入力データがないため保存をキャンセルしました。")
            else:
                with st.spinner("クラウドへ保存中..."):
                    success, saved_time = robust_api_call(
                        save_draft_to_sheet, 
                        username=user_id, 
                        draft_data=draft,
                        fallback_value=(False, None)
                    )
                    if success:
                        st.session_state['last_saved_time'] = saved_time
                        st.success("✅ クラウド保存完了！")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("保存に失敗しました。")
            
        if c2.button("📂 復元", use_container_width=True):
            with st.spinner("クラウドから復元中..."):
                draft, saved_time = robust_api_call(
                    load_draft_from_sheet, 
                    username=user_id,
                    fallback_value=(None, None)
                )
                
                if draft:
                    for k, v in draft.items():
                        st.session_state[k] = v
                    st.session_state['last_saved_time'] = saved_time
                    st.success("✅ 復元しました！")
                    time.sleep(1.5)
                    st.rerun() 
                else:
                    st.warning("クラウドに保存データがありません")
                    
        if st.button("🗑️ 保存データを削除", use_container_width=True):
            with st.spinner("削除中..."):
                success = robust_api_call(
                    delete_draft_from_sheet,
                    username=user_id,
                    fallback_value=False
                )
                if success:
                    st.session_state['last_saved_time'] = None
                    st.success("✅ 削除しました！")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("削除に失敗しました")
        st.divider()
        st.warning("🚨 **【重要】離席時の注意**\n\n一定時間でサーバーがスリープします。**入力途中で離席する際は必ず「☁️ 保存」を押してください！**")

    if last_saved_time:
        st.error("⚠️ **前回中断した入力データがクラウドに残っています！** 続きから入力する場合は、左メニューの「📂 復元」を先に押してください。")

    student_df = cached_get_student_master()
    if not student_df.empty:
        student_options = (student_df['生徒ID'].astype(str) + " - " + student_df['生徒名']).tolist()
    else:
        student_options = []
        st.warning("生徒データが取得できませんでした。")

    teacher_names = cached_get_teacher_names()
    text_options = list(cached_get_textbook_master().keys())
    
    quiz_details = cached_get_quiz_master()
    quiz_names = []
    for key in quiz_details.keys():
        if "_" in key:
            q_name = key.split("_", 1)[0]
            if q_name not in quiz_names:
                quiz_names.append(q_name)
    if not quiz_names:
        quiz_names = ["設定なし"]

    df_all_logs = cached_get_all_logs()

    st.write("### 🗂️ 授業コマの管理")
    num_blocks = st.session_state.get('num_blocks', 1)

    col_add, col_del, _ = st.columns([2, 2, 6])
    with col_add:
        st.button("➕ 新しいコマ（タブ）を追加", use_container_width=True, on_click=add_tab)
    with col_del:
        if num_blocks > 1:
            st.button("➖ 最後のタブを削除", use_container_width=True, on_click=remove_tab)

    tabs = st.tabs([f"📝 コマ {b+1}" for b in range(num_blocks)])
    
    single_save_triggered = None
    all_save_triggered = None

    for b in range(num_blocks):
        with tabs[b]:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
                
                date = c1.date_input("授業日", datetime.date.today(), key=f"class_date_{b}")
                teacher_name = c2.selectbox("👨‍🏫 担当講師", teacher_names, index=None, placeholder="講師を選択", key=f"sb_teacher_{b}")
                class_type = c3.radio("👥 授業形態", ["1:1", "1:2", "1:3"], horizontal=True, key=f"class_type_{b}")
                
                time_slots = [
                    "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                    "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
                    "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
                ]
                class_slot = c4.selectbox("⏰ 授業コマ", time_slots, index=None, placeholder="コマを選択", key=f"sb_class_slot_{b}")

            if not teacher_name or not class_slot:
                st.info(f"👆 コマ {b+1} の「担当講師」と「授業コマ」を選択してください。")
                continue 

            num_students = int(class_type.split(":")[1])
            st.divider()
            cols = st.columns(num_students)
            input_data_list = []

            for i in range(num_students):
                with cols[i]:
                    with st.container(border=True):
                        is_saved = st.session_state.get(f"saved_flag_{b}_{i}", False)
                        saved_name = st.session_state.get(f"saved_name_{b}_{i}", "生徒")

                        if is_saved:
                            st.success(f"✅ {saved_name} さんの記録は保存済みです。")
                            st.info("💡 修正が必要な場合は、左メニューの「🛠️ 授業記録の修正」から行ってください。")
                        else:
                            student_choices = ["🆕 新規登録（通常）", "🔰 新規登録（体験）"] + student_options
                            selected_student = st.selectbox("生徒名", student_choices, index=None, placeholder="生徒を選択", key=f"sel_student_{b}_{i}")
                            
                            student_id = None
                            name = None
                            is_trial = False

                            if selected_student == "🆕 新規登録（通常）":
                                name = st.text_input("新しい生徒の名前", key=f"new_name_{b}_{i}")
                                student_id = "NEW" 
                            elif selected_student == "🔰 新規登録（体験）":
                                name = st.text_input("体験生徒の名前", key=f"new_name_{b}_{i}")
                                student_id = "TRIAL"
                                is_trial = True 
                            elif selected_student:
                                student_id = selected_student.split(" - ")[0]
                                name = selected_student.split(" - ")[1]

                            if name:
                                type_advice_dict = cached_get_type_advice()
                                student_type_str = ""
                                if not student_df.empty and 'タイプ' in student_df.columns:
                                    row = student_df[student_df['生徒名'] == name]
                                    if not row.empty:
                                        student_type_str = str(row.iloc[0].get('タイプ', ''))
                                
                                if student_type_str and student_type_str.lower() != "nan":
                                    advices = []
                                    for t_key, t_adv in type_advice_dict.items():
                                        if t_key in student_type_str:
                                            advices.append(f"・{t_adv}")
                                    
                                    if advices:
                                        st.info("💡 **指導アドバイス（生徒タイプ別）**\n" + "\n".join(advices))

                                attendance = st.selectbox("📅 出欠状況", ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"], key=f"att_{b}_{i}")
                                late_time = st.number_input("⏰ 遅刻時間 (分)", min_value=0, value=0, step=5, key=f"late_{b}_{i}")

                                if "欠席" in attendance:
                                    st.warning("欠席のため、進捗・テスト入力はスキップされます。")
                                    input_data_list.append({
                                        "original_idx": i, 
                                        "student_id" : student_id, "name": name, "subject": "-", "text_name": "-", "advanced_p": "-", 
                                        "quiz_records": [], "w_nums_for_sheet": "", "attendance": attendance,
                                        "late_time": late_time, "concentration": "-", "reaction": "-",
                                        "advice": "-", "parent_msg": "-", "next_handover": "-",
                                        "assigned_p": 0, "completed_p": 0, "motivation_rank": 0, 
                                        "next_hw_text": "-", "next_hw_pages": "-", "is_trial": is_trial,
                                        "hw_reason": "", "hw_fix": "", "next_bring": ""
                                    })
                                else:
                                    subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], index=None, placeholder="科目を選択", key=f"sub_{b}_{i}")
                                    
                                    if not subject:
                                        st.info("👆 科目を選択すると詳細入力が開きます")
                                    else:
                                        assigned_p = 0
                                        completed_p = 0
                                        last_page_num = 0

                                        filtered_text_options = []
                                        for t in text_options:
                                            if "Myeトレ" in t:
                                                if subject in t: 
                                                    filtered_text_options.append(t)
                                            else:
                                                filtered_text_options.append(t)
                                        
                                        with st.expander("🔍 1. 前回データ確認 ＆ 宿題チェック", expanded=not is_trial):
                                            if is_trial:
                                                st.info("🔰 体験生モード：前回の引き継ぎ・宿題確認はスキップされます。")
                                                hw_reason_val = ""
                                                hw_fix_val = ""
                                            else:
                                                last_note, last_hw_text, last_hw_pages, last_page = "", "", "", "0"
                                                last_teacher = "不明"
                                                last_date_str = "過去データなし"
                                                
                                                if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns:
                                                    name_col = '生徒名' if '生徒名' in df_all_logs.columns else '名前'
                                                    df_s = df_all_logs[(df_all_logs[name_col] == name) & (df_all_logs['科目'] == subject)].copy()
                                                    
                                                    if not df_s.empty:
                                                        df_s['日時'] = pd.to_datetime(df_s['日時'], format='mixed', errors='coerce')
                                                        last_row = df_s.sort_values('日時', ascending=False).iloc[0]
                                                        
                                                        last_teacher = str(last_row.get('担当講師', '不明'))
                                                        last_date_str = last_row['日時'].strftime('%Y/%m/%d') if pd.notna(last_row['日時']) else "不明"
                                                        
                                                        last_note = str(last_row.get('次回への引継ぎ事項', ''))
                                                        if last_note in ["nan", "", "-"]: last_note = "特になし"
                                                        
                                                        last_hw_text = str(last_row.get('次回の宿題テキスト', ''))
                                                        if last_hw_text in ["nan", "", "-"]: last_hw_text = "なし"
                                                        
                                                        last_hw_pages = str(last_row.get('次回の宿題ページ数', ''))
                                                        if last_hw_pages in ["nan", "", "-"]: last_hw_pages = "なし"
                                                        
                                                        last_page = str(last_row.get('終了ページ', ''))
                                                        if last_page in ["nan", "", "-"]: last_page = "なし"
                                                
                                                last_page_num = int(last_page) if str(last_page).isdigit() else 0
                                                
                                                formatted_last_page = str(last_page).replace('\n', '  \n')
                                                formatted_last_hw_pages = str(last_hw_pages).replace('\n', '  \n')

                                                st.markdown(f"**📅 前回: {last_date_str} （👨‍🏫 担当: {last_teacher}先生）**")
                                                st.info(
                                                    f"📖 **前回の進捗:** {formatted_last_page}  \n"
                                                    f"📚 **出した宿題:** {last_hw_text}  \n"
                                                    f"🎯 **宿題範囲:** {formatted_last_hw_pages}  \n\n"
                                                    f"💬 **引継ぎメモ:** \n{last_note}"
                                                )
                                                
                                                assigned_hw_list = []
                                                if str(last_hw_pages).strip() and str(last_hw_pages).strip() not in ["-", "なし"]:
                                                    for line in str(last_hw_pages).split('\n'):
                                                        match = re.search(r'(?:(.*?)[:：]\s*)?[P\.]*(\d+)\s*[〜~-]\s*(\d+)', line)
                                                        if match:
                                                            t_name = match.group(1) or str(last_hw_text).split('、')[0]
                                                            a_start, a_end = int(match.group(2)), int(match.group(3))
                                                            if a_end >= a_start:
                                                                pages = a_end - a_start + 1
                                                                assigned_p += pages
                                                                assigned_hw_list.append({"text": t_name.strip(), "start": a_start, "end": a_end, "pages": pages})

                                                st.write("📝 **今回の宿題達成状況**")
                                                
                                                c_chk1, c_chk2 = st.columns(2)
                                                with c_chk1:
                                                    is_continuous = st.checkbox("🔄 前回を引き継ぐ", key=f"cont_{b}_{i}")
                                                with c_chk2:
                                                    is_hw_forgotten = st.checkbox("❌ 忘れた・やってない", key=f"hw_forgot_{b}_{i}")
                                                
                                                if is_continuous:
                                                    st.caption("※次回の宿題指示にそのまま引き継ぎます。")
                                                    assigned_p = 0 
                                                elif is_hw_forgotten:
                                                    completed_p = 0
                                                else:
                                                    if not assigned_hw_list:
                                                        st.caption("※手動入力欄")
                                                        c_hw1, c_hw2 = st.columns(2)
                                                        with c_hw1:
                                                            done_start = st.number_input("やった開始P", min_value=0, value=0, key=f"done_start_{b}_{i}")
                                                        with c_hw2:
                                                            done_end = st.number_input("やった終了P", min_value=0, value=0, key=f"done_end_{b}_{i}")
                                                        if done_end >= done_start and done_end > 0:
                                                            completed_p = done_end - done_start + 1
                                                    else:
                                                        for h_idx, hw in enumerate(assigned_hw_list):
                                                            st.caption(f"📘 {hw['text']} (指示: P.{hw['start']}〜{hw['end']})")
                                                            c_hw1, c_hw2 = st.columns(2)
                                                            with c_hw1:
                                                                d_start = st.number_input("やった開始P", min_value=0, value=hw['start'], key=f"d_s_{b}_{i}_{h_idx}")
                                                            with c_hw2:
                                                                d_end = st.number_input("やった終了P", min_value=0, value=hw['end'], key=f"d_e_{b}_{i}_{h_idx}")
                                                            
                                                            if d_end >= d_start and d_end > 0:
                                                                completed_p += (d_end - d_start + 1)
                                                        
                                                    st.caption(f"📊 出した宿題: **{assigned_p}** P / やった宿題: **{completed_p}** P")

                                                hw_reason_val = ""
                                                hw_fix_val = ""
                                                
                                                if (assigned_p > 0 and completed_p < assigned_p) or is_hw_forgotten:
                                                    st.warning("⚠️ 宿題が未達成です。原因の分析と修正策を記録してください。")
                                                    r_col1, r_col2 = st.columns(2)
                                                    
                                                    with r_col1:
                                                        reason_sel = st.selectbox("未達成の理由", ["", "難易度(難しかった)", "文量(多かった)", "時間管理(サボり・多忙)", "事故(体調・急用)", "その他"], key=f"hw_reason_sel_{b}_{i}")
                                                        if reason_sel == "その他":
                                                            reason_other = st.text_input("理由（その他）", key=f"hw_reason_other_{b}_{i}")
                                                            hw_reason_val = f"その他: {reason_other}" if reason_other else "その他"
                                                        else:
                                                            hw_reason_val = reason_sel
                                                        
                                                    with r_col2:
                                                        fix_sel = st.selectbox("本日の修正策", ["", "文量調整(減らす)", "期限延長(スライド)", "内容変更(基礎へ戻る)", "再約束(マインドセット)", "その他"], key=f"hw_fix_sel_{b}_{i}")
                                                        if fix_sel == "その他":
                                                            fix_other = st.text_input("修正策（その他）", key=f"hw_fix_other_{b}_{i}")
                                                            hw_fix_val = f"その他: {fix_other}" if fix_other else "その他"
                                                        else:
                                                            hw_fix_val = fix_sel

                                        with st.expander("📚 2. 今回の授業進捗 ＆ 💯 小テスト", expanded=True):
                                            st.write("📚 **使用テキストと進捗**")
                                            usage_text_options = ["🆕 新規テキスト入力"] + filtered_text_options
                                            selected_texts = st.multiselect("使用テキスト (複数可)", usage_text_options, key=f"texts_{b}_{i}")
                                            
                                            if "🆕 新規テキスト入力" in selected_texts:
                                                new_usage_text = st.text_input("📝 新しいテキスト名を入力", key=f"new_usage_text_{b}_{i}")
                                                if new_usage_text:
                                                    robust_api_call(add_new_textbook, new_usage_text)
                                                    selected_texts.remove("🆕 新規テキスト入力")
                                                    if new_usage_text not in selected_texts:
                                                        selected_texts.append(new_usage_text)
                                                    cached_get_textbook_master.clear()

                                            advanced_p_list = []
                                            if selected_texts and "🆕 新規テキスト入力" not in selected_texts:
                                                text_name_str = "、".join(selected_texts)
                                                for t_idx, text_name in enumerate(selected_texts):
                                                    st.caption(f"📘 {text_name} の進捗")
                                                    
                                                    # 🌟 【天才機能】辞書（dict）で送られてきた単元名をリストに変換！
                                                    if "Myeトレ" in text_name:
                                                        units_raw = cached_get_textbook_master().get(text_name, {})
                                                        
                                                        if isinstance(units_raw, dict):
                                                            # 辞書の場合は「値（単元名）」をリストにする。単元名が空なら章番号にする安全設計
                                                            unit_options = [str(v).strip() if str(v).strip() else str(k).strip() for k, v in units_raw.items()]
                                                        elif isinstance(units_raw, str):
                                                            unit_options = [u.strip() for u in units_raw.replace('、', ',').split(',') if u.strip()]
                                                        elif isinstance(units_raw, list):
                                                            unit_options = [str(u).strip() for u in units_raw if str(u).strip() != ""]
                                                        else:
                                                            unit_options = []
                                                        
                                                        adv_unit = st.selectbox("実施した単元を選択してください", [""] + unit_options, key=f"adv_unit_{b}_{i}_{t_idx}")
                                                        
                                                        if adv_unit:
                                                            advanced_p_list.append(f"{text_name}: {adv_unit}")
                                                        else:
                                                            advanced_p_list.append(f"{text_name}: -")
                                                    else:
                                                        col_adv1, col_adv2 = st.columns(2)
                                                        with col_adv1:
                                                            adv_start = st.number_input(f"開始P", min_value=0, value=last_page_num, key=f"adv_start_{b}_{i}_{t_idx}")
                                                        with col_adv2:
                                                            adv_end = st.number_input(f"終了P", min_value=0, value=last_page_num, key=f"adv_end_{b}_{i}_{t_idx}")
                                                        
                                                        if adv_end >= adv_start and adv_end > 0:
                                                            advanced_p_list.append(f"{text_name}: P.{adv_start}〜{adv_end}")
                                                        else:
                                                            advanced_p_list.append(f"{text_name}: -")
                                                advanced_p_str = "\n".join(advanced_p_list)
                                            else:
                                                text_name_str = "-"
                                                advanced_p_str = "-"
                                                st.info("👆 テキストを選択すると進捗入力欄が表示されます")
                                            
                                            st.divider()
                                            
                                            num_quizzes = st.number_input("💯 小テスト実施回数", min_value=0, max_value=5, value=0, step=1, key=f"num_q_{b}_{i}")
                                            quiz_records = []
                                            w_nums_for_sheet_list = []
                                            current_quiz_pts = 0 
                                            
                                            if num_quizzes > 0:
                                                for q_idx in range(num_quizzes):
                                                    with st.container(border=True):
                                                        st.write(f"**【小テスト {q_idx + 1}】**")
                                                        q_name = st.selectbox(f"テストの種類", quiz_names, index=None, placeholder="小テストを選択", key=f"q_name_{b}_{i}_{q_idx}")
                                                        
                                                        current_max = 100 
                                                        if q_name:
                                                            matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_name}_")]
                                                            if matched_marks:
                                                                current_max = int(pd.Series(matched_marks).mode()[0])

                                                        col_q1, col_q2 = st.columns(2)
                                                        with col_q1:
                                                            target_chap = st.number_input(f"実施した単元/回", min_value=1, value=1, step=1, key=f"q_chap_{b}_{i}_{q_idx}")
                                                        with col_q2:
                                                            score = st.number_input(f"点数 (/{current_max}点満点)", min_value=0, max_value=current_max, value=current_max, step=1, key=f"q_score_{b}_{i}_{q_idx}")
                                                        
                                                        w_nums = st.text_input(f"ミス問題番号 (任意)", key=f"w_{b}_{i}_{q_idx}")
                                                        
                                                        quiz_records.append({
                                                            "quiz_name": q_name or "不明", "unit": target_chap, "score": score
                                                        })
                                                        if w_nums:
                                                            w_nums_for_sheet_list.append(w_nums)
                                                        current_quiz_pts += calculate_quiz_points(score, q_name, quiz_details)
                                            
                                            w_nums_for_sheet = ",".join(w_nums_for_sheet_list)
                                            today_hw_rate = calculate_hw_rate(assigned_p, completed_p)
                                            motivation_rank = calculate_motivation_rank(today_hw_rate, current_quiz_pts, 0)

                                        with st.expander("🧠 3. 授業の様子 ＆ 🚀 次回の宿題・コメント", expanded=True):
                                            st.write("🧠 **授業中の様子・評価**")
                                            col_eval1, col_eval2 = st.columns(2)
                                            with col_eval1:
                                                concentration = st.selectbox("集中力", ["超集中", "前向き", "疲労気味", "ムラあり", "集中できない"], index=None, placeholder="選択してください", key=f"conc_{b}_{i}")
                                            with col_eval2:
                                                reaction = st.selectbox("ミスへの反応", ["原因を分析した", "悔しがった", "放置しようとした"], index=None, placeholder="選択してください", key=f"reac_{b}_{i}")
                                            
                                            st.divider()

                                            selected_hw_text_str = "-"
                                            next_hw_pages_str = "-"
                                            
                                            if is_trial:
                                                st.info("🔰 体験生モード：次回の宿題指示はスキップされます。")
                                            else:
                                                st.write("🚀 **次回の宿題指示**")
                                                if is_continuous:
                                                    selected_hw_text_str = str(last_hw_text)
                                                    next_hw_pages_str = str(last_hw_pages)
                                                    st.info(f"🔄 【自動引き継ぎ】\n📚 テキスト: **{selected_hw_text_str}**\n🎯 範囲: \n{next_hw_pages_str}")
                                                else:
                                                    selected_hw_texts = st.multiselect("次回の宿題テキスト (複数可)", filtered_text_options, key=f"hw_texts_{b}_{i}")

                                                    next_hw_pages_list = []
                                                    if selected_hw_texts:
                                                        for t_idx, hw_text in enumerate(selected_hw_texts):
                                                            st.write(f"📘 **{hw_text}** の宿題")
                                                            
                                                            # 🌟 宿題側も天才機能（辞書→リスト化）を追加！
                                                            if "Myeトレ" in hw_text:
                                                                units_raw = cached_get_textbook_master().get(hw_text, {})
                                                                
                                                                if isinstance(units_raw, dict):
                                                                    unit_options = [str(v).strip() if str(v).strip() else str(k).strip() for k, v in units_raw.items()]
                                                                elif isinstance(units_raw, str):
                                                                    unit_options = [u.strip() for u in units_raw.replace('、', ',').split(',') if u.strip()]
                                                                elif isinstance(units_raw, list):
                                                                    unit_options = [str(u).strip() for u in units_raw if str(u).strip() != ""]
                                                                else:
                                                                    unit_options = []
                                                                
                                                                hw_units = st.multiselect("宿題にする単元を選択してください (複数可)", unit_options, key=f"hw_unit_{b}_{i}_{t_idx}")
                                                                if hw_units:
                                                                    next_hw_pages_list.append(f"{hw_text}: {', '.join(hw_units)}")
                                                            else:
                                                                num_ranges = st.number_input(f"出す範囲の数 (飛び石対応)", min_value=1, max_value=5, value=1, key=f"hw_ranges_num_{b}_{i}_{t_idx}")
                                                                
                                                                for r_idx in range(num_ranges):
                                                                    n_s_col, n_e_col = st.columns(2)
                                                                    next_start = n_s_col.number_input(f"開始P ({r_idx+1})", min_value=0, value=0, key=f"n_s_{b}_{i}_{t_idx}_{r_idx}")
                                                                    next_end = n_e_col.number_input(f"終了P ({r_idx+1})", min_value=0, value=0, key=f"n_e_{b}_{i}_{t_idx}_{r_idx}")
                                                                    
                                                                    if next_end >= next_start and next_end > 0:
                                                                        next_hw_pages_list.append(f"{hw_text}: P.{next_start}〜{next_end}")
                                                                    
                                                        next_hw_pages_str = "\n".join(next_hw_pages_list) if next_hw_pages_list else "-"
                                                        selected_hw_text_str = "、".join(selected_hw_texts)
                                                    else:
                                                        st.info("👆 テキストを選択するとページ入力欄が表示されます")

                                            st.divider()
                                            st.write("🎒 **次回の持ち物**")
                                            next_bring_val = st.text_input(
                                                "必要な持ち物（テキスト、プリント、ノートなど）", 
                                                key=f"bring_{b}_{i}", 
                                                placeholder="例: 数学の教科書、過去問プリント"
                                            )

                                            st.divider()
                                            if is_trial:
                                                st.write("💬 **体験授業コメント**")
                                                advice = st.text_area("🌟 生徒の長所・褒めた点", height=80, key=f"advc_{b}_{i}")
                                                parent_msg = st.text_area("👪 保護者へお伝えしたいこと", height=80, key=f"p_msg_{b}_{i}")
                                                next_handover = st.text_area("🔄 入塾に向けた課題・特記事項", height=80, key=f"next_h_{b}_{i}")
                                            else:
                                                st.write("💬 **コメント事項**")
                                                advice = st.text_area("🗣️ 授業でのアドバイス（褒めた点など）", height=80, key=f"advc_{b}_{i}")
                                                parent_msg = st.text_area("👪 保護者への連絡事項", height=80, key=f"p_msg_{b}_{i}")
                                                next_handover = st.text_area("🔄 次回への引継ぎ事項", height=80, key=f"next_h_{b}_{i}")

                                        input_data_list.append({
                                            "original_idx": i, 
                                            "student_id": student_id, "name": name, "subject": subject, "text_name": text_name_str,
                                            "advanced_p": advanced_p_str, "quiz_records": quiz_records, 
                                            "w_nums_for_sheet": w_nums_for_sheet, "attendance": attendance,
                                            "late_time": late_time, "concentration": concentration or "-", "reaction": reaction or "-",
                                            "advice": advice, "parent_msg": parent_msg, "next_handover": next_handover,
                                            "assigned_p": assigned_p, "completed_p": completed_p, "advanced_p_str": advanced_p_str,
                                            "motivation_rank": motivation_rank, 
                                            "next_hw_text": selected_hw_text_str, 
                                            "next_hw_pages": next_hw_pages_str,
                                            "is_trial": is_trial,
                                            "hw_reason": hw_reason_val,
                                            "hw_fix": hw_fix_val,
                                            "next_bring": next_bring_val
                                        })

                                        st.write("")
                                        
                                        if st.button(f"👤 {name} の記録だけを個別に保存", key=f"save_single_{b}_{i}", use_container_width=True):
                                            with st.status(f"{name} のデータを保存中...", expanded=True) as status:
                                                success = robust_api_call(
                                                    save_to_spreadsheet,
                                                    student_id=student_id, name=name, subject=subject, text_name=text_name_str,
                                                    advanced_p=advanced_p_str, quiz_records=[], date=date, 
                                                    teacher_name=teacher_name, class_type=class_type, attendance=attendance,
                                                    class_slot=class_slot, advice=advice, parent_msg=parent_msg,
                                                    next_handover=next_handover, assigned_p=assigned_p, completed_p=completed_p, 
                                                    motivation_rank=motivation_rank, next_hw_text=selected_hw_text_str,
                                                    next_hw_pages=next_hw_pages_str, late_time=late_time,        
                                                    concentration=concentration or "-", reaction=reaction or "-",
                                                    hw_reason=hw_reason_val,
                                                    hw_fix=hw_fix_val,
                                                    next_bring=next_bring_val,
                                                    fallback_value=False 
                                                )

                                                if success: 
                                                    if quiz_records and len(quiz_records) > 0:
                                                        for q in quiz_records:
                                                            robust_api_call(
                                                                save_quiz_to_dedicated_sheet,
                                                                date_str=date.strftime("%Y/%m/%d"), student_name=name, text_name=q["quiz_name"],
                                                                chapter=q["unit"], score=q["score"], w_nums="", mode="授業内"
                                                            )
                                                    
                                                    if attendance != "欠席（振替なし）" and "欠席" not in attendance and not is_trial:
                                                        try:
                                                            robust_api_call(update_student_homework_rate, name, subject, assigned_p, completed_p)
                                                        except Exception:
                                                            pass 
                                                    
                                                    status.update(label="保存完了！", state="complete", expanded=False)
                                                    st.success(f"✅ {name} の記録を保存しました！")
                                                    
                                                    st.session_state[f"saved_flag_{b}_{i}"] = True
                                                    st.session_state[f"saved_name_{b}_{i}"] = name
                                                    single_save_triggered = True
                                                else:
                                                    status.update(label="保存失敗", state="error", expanded=True)
                                                    st.error(f"❌ {name} の保存に失敗しました。通信状況を確認して再度お試しください。データは保持されています。")

            st.divider()
            
            if len(input_data_list) > 0:
                actual_attendees = sum(1 for data in input_data_list if "欠席" not in data["attendance"])
                actual_class_type = f"1:{actual_attendees}" if actual_attendees > 0 else class_type
                
                if actual_attendees < len(input_data_list) and actual_attendees > 0:
                    st.info(f"💡 欠席者がいるため、実際の授業形態は「{actual_class_type}」として記録されます。")

                btn_label = f"🚀 コマ {b+1} の全員の記録をまとめて保存する" if len(input_data_list) == num_students else f"🚀 コマ {b+1} の【未保存の {len(input_data_list)}名】をまとめて保存する"

                if st.button(btn_label, type="primary", key=f"save_all_{b}", use_container_width=True):
                    with st.status("データを保存中...", expanded=True) as status:
                        all_success = True
                        for data in input_data_list:
                            o_idx = data["original_idx"]
                            
                            if "欠席" in data.get("attendance", ""):
                                st.session_state[f"saved_flag_{b}_{o_idx}"] = True
                                continue

                            if st.session_state.get(f"saved_flag_{b}_{o_idx}", False):
                                continue

                            success = robust_api_call(
                                save_to_spreadsheet,
                                student_id=data.get("student_id", ""), name=data.get("name", ""), subject=data.get("subject", ""),
                                text_name=data.get("text_name_str", data.get("text_name", "")), advanced_p=data.get("advanced_p_str", ""),
                                quiz_records=[], date=date, teacher_name=teacher_name, class_type=actual_class_type,  
                                attendance=data.get("attendance", ""), class_slot=class_slot, advice=data.get("advice", ""),
                                parent_msg=data.get("parent_msg", ""), next_handover=data.get("next_handover", ""),
                                assigned_p=data.get("assigned_p", 0), completed_p=data.get("completed_p", 0), 
                                motivation_rank=data.get("motivation_rank", ""), next_hw_text=data.get("next_hw_text", ""),
                                next_hw_pages=data.get("next_hw_pages", ""), late_time=data.get("late_time", ""),        
                                concentration=data.get("concentration", ""), reaction=data.get("reaction", ""),
                                hw_reason=data.get("hw_reason", ""),
                                hw_fix=data.get("hw_fix", ""),
                                next_bring=data.get("next_bring", ""),
                                fallback_value=False
                            )

                            if success:
                                if data.get("quiz_records") and len(data["quiz_records"]) > 0:
                                    for q in data["quiz_records"]:
                                        robust_api_call(
                                            save_quiz_to_dedicated_sheet,
                                            date_str=date.strftime("%Y/%m/%d"), student_name=data["name"], text_name=q["quiz_name"],
                                            chapter=q["unit"], score=q["score"], w_nums="", mode="授業内"
                                        )
                                
                                if data["attendance"] != "欠席（振替なし）" and "欠席" not in data["attendance"] and not data.get("is_trial"):
                                    try:
                                        robust_api_call(update_student_homework_rate, data["name"], data["subject"], data["assigned_p"], data["completed_p"])
                                    except Exception:
                                        pass 
                                        
                                st.session_state[f"saved_flag_{b}_{o_idx}"] = True
                                st.session_state[f"saved_name_{b}_{o_idx}"] = data["name"]
                            else:
                                all_success = False
                                st.error(f"❌ {data['name']} さんの保存に失敗しました。")

                        if all_success:
                            status.update(label="未保存者の保存完了！", state="complete", expanded=False)
                            st.success(f"✅ コマ {b+1}（{actual_attendees}名）の記録を保存しました！")
                            st.session_state['last_saved_time'] = None 
                            all_save_triggered = (b, num_students)
                        else:
                            status.update(label="一部の保存に失敗しました", state="error", expanded=True)
                            st.warning("⚠️ 失敗した生徒のデータは画面に残っています。通信状況を確認し「個別に保存」から再試行してください。")

            saved_count = sum(1 for idx in range(num_students) if st.session_state.get(f"saved_flag_{b}_{idx}", False))
            if saved_count == num_students and num_students > 0 and not all_save_triggered:
                st.success("🎉 このコマの全員の入力が完了しました！画面をリセットします...")
                all_save_triggered = (b, num_students)

    if all_save_triggered:
        b_idx, students_count = all_save_triggered
        for k in ["class_date", "sb_teacher", "class_type", "sb_class_slot"]:
            if f"{k}_{b_idx}" in st.session_state:
                del st.session_state[f"{k}_{b_idx}"]

        target_prefixes = [
            "sel_student", "new_name", "att", "late", "sub", "cont", "hw_forgot", 
            "done_start", "done_end", "texts", "new_usage_text", "adv_start", 
            "adv_end", "num_q", "q_name", "q_chap", "q_score", "w", 
            "conc", "reac", "hw_texts", "new_hw_text", "hw_ranges_num", 
            "n_s", "n_e", "advc", "p_msg", "next_h", "d_s", "d_e",
            "saved_flag", "saved_name", "hw_reason", "hw_fix", "bring", "adv_unit", "hw_unit"
        ]
        for i_idx in range(students_count):
            for key in list(st.session_state.keys()):
                for p in target_prefixes:
                    if key == f"{p}_{b_idx}_{i_idx}" or key.startswith(f"{p}_{b_idx}_{i_idx}_"):
                        del st.session_state[key]
                        break
        
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()

    elif single_save_triggered:
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()