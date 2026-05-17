import streamlit as st
import datetime
import time
import re
import os
import pickle
import pandas as pd

from utils.g_sheets import (
    get_student_master,
    get_all_teacher_names,
    save_to_spreadsheet, 
    get_last_page_from_sheet, 
    update_student_homework_rate,
    get_last_handover,
    get_last_homework_info,  
    add_new_textbook,        
    get_textbook_master,
    save_quiz_to_dedicated_sheet,
    get_quiz_master_dict 
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

# 🌟 新しい入力項目を一時保存対象に追加（タブ数も記憶させます）
DRAFT_PREFIXES = (
    "num_blocks", "class_date", "class_type", 
    "sb_", "sel_student", "new_name", "att", "late", "sub", "texts", "new_usage_text", 
    "adv_start", "adv_end", "num_q", "q_name", "q_chap", "q_score", "w",
    "cont", "done_start", "done_end", "conc", "reac", "hw_texts", "new_hw_text", 
    "n_start", "n_end", "advc", "p_msg", "next_h", "d_s", "d_e", "n_s", "n_e", "hw_ranges_num"
)

def render_multi_input_page():
    user_id = st.session_state.get('user_id', st.session_state.get('username', 'default_user'))
    draft_file = f"draft_{user_id}.pkl"

    with st.sidebar:
        st.header("💾 鉄壁の一時保存メニュー")
        st.caption("アプリが落ちても、ブラウザを閉じても復元できます！")
        
        c1, c2 = st.columns(2)
        if c1.button("💾 保存", use_container_width=True):
            draft = {}
            for k, v in st.session_state.items():
                if k.startswith(DRAFT_PREFIXES):
                    draft[k] = v
                    
            with open(draft_file, "wb") as f:
                pickle.dump(draft, f)
                
            st.success("鉄壁保存しました！")
            
        if c2.button("📂 復元", use_container_width=True):
            if os.path.exists(draft_file):
                with open(draft_file, "rb") as f:
                    draft = pickle.load(f)
                    
                for k, v in draft.items():
                    st.session_state[k] = v
                st.success("復元しました！")
                time.sleep(1)
                st.rerun() 
            else:
                st.warning("保存データがありません")
                
        if st.button("🗑️ 保存データを削除", use_container_width=True):
            if os.path.exists(draft_file):
                os.remove(draft_file)
                st.success("削除しました！")
                time.sleep(1)
                st.rerun()
            else:
                st.info("削除するデータがありません")
        st.divider()

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


    # ==========================================
    # 🌟 【新機能】授業コマ（タブ）の追加・削除コントロール
    # ==========================================
    st.write("### 🗂️ 授業コマの管理")
    num_blocks = st.session_state.get('num_blocks', 1)

    col_add, col_del, _ = st.columns([2, 2, 6])
    with col_add:
        if st.button("➕ 新しいコマ（タブ）を追加", use_container_width=True):
            st.session_state['num_blocks'] = num_blocks + 1
            st.rerun()
    with col_del:
        if num_blocks > 1:
            if st.button("➖ 最後のタブを削除", use_container_width=True):
                # 削除するタブの入力データをきれいにお掃除
                b_to_delete = num_blocks - 1
                for key in list(st.session_state.keys()):
                    if f"_{b_to_delete}" in key:
                        del st.session_state[key]
                st.session_state['num_blocks'] = num_blocks - 1
                st.rerun()

    # タブの生成
    tabs = st.tabs([f"📝 コマ {b+1}" for b in range(num_blocks)])
    
    # お掃除を一番最後に遅らせるための「しおり」
    single_save_triggered = None
    all_save_triggered = None

    for b in range(num_blocks):
        with tabs[b]:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
                # 🌟 すべての入力キーに「b（何番目のタブか）」を割り振って完全独立させる！
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
                continue # 選択されるまでこのタブの描画はストップ

            num_students = int(class_type.split(":")[1])
            st.divider()
            cols = st.columns(num_students)
            input_data_list = []

            for i in range(num_students):
                with cols[i]:
                    with st.container(border=True):
                        selected_student = st.selectbox("生徒名", ["🆕 新規登録"] + student_options, index=None, placeholder="生徒を選択", key=f"sel_student_{b}_{i}")
                        
                        student_id = None
                        name = None

                        if selected_student == "🆕 新規登録":
                            name = st.text_input("新しい生徒の名前", key=f"new_name_{b}_{i}")
                            student_id = "NEW" 
                        elif selected_student:
                            student_id = selected_student.split(" - ")[0]
                            name = selected_student.split(" - ")[1]

                        if name:
                            attendance = st.selectbox("📅 出欠状況", ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"], key=f"att_{b}_{i}")
                            late_time = st.number_input("⏰ 遅刻時間 (分)", min_value=0, value=0, step=5, key=f"late_{b}_{i}")

                            if "欠席" in attendance:
                                st.warning("欠席のため、進捗・テスト入力はスキップされます。")
                                input_data_list.append({
                                    "student_id" : student_id, "name": name, "subject": "-", "text_name": "-", "advanced_p": "-", 
                                    "quiz_records": [], "w_nums_for_sheet": "", "attendance": attendance,
                                    "late_time": late_time, "concentration": "-", "reaction": "-",
                                    "advice": "-", "parent_msg": "-", "next_handover": "-",
                                    "assigned_p": 0, "completed_p": 0, "motivation_rank": 0, 
                                    "next_hw_text": "-", "next_hw_pages": "-"
                                })
                            else:
                                subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], index=None, placeholder="科目を選択", key=f"sub_{b}_{i}")
                                
                                if not subject:
                                    st.info("👆 科目を選択すると詳細入力が開きます")
                                else:
                                    cache_key = f"prev_data_{name}_{subject}"
                                    if cache_key not in st.session_state:
                                        with st.spinner("☁️ 過去のデータを読み込み中..."):
                                            st.session_state[cache_key] = {
                                                "note": robust_api_call(get_last_handover, name, subject),
                                                "hw_info": robust_api_call(get_last_homework_info, name, subject),
                                                "page": robust_api_call(get_last_page_from_sheet, name, subject)
                                            }
                                    
                                    cached_data = st.session_state[cache_key]
                                    last_note = cached_data["note"]
                                    last_hw_text, last_hw_pages = cached_data["hw_info"]
                                    last_page = cached_data["page"]
                                    
                                    last_page_num = int(last_page) if str(last_page).isdigit() else 0
                                    formatted_last_page = str(last_page).replace('\n', '  \n')
                                    formatted_last_hw_pages = str(last_hw_pages).replace('\n', '  \n')

                                    st.info(
                                        f"💡 **【前回 ({subject}) の引継ぎ・宿題・進捗】**\n\n"
                                        f"📖 **前回の授業進捗:**  \n{formatted_last_page}\n\n"
                                        f"📚 **宿題テキスト:** {last_hw_text}\n"
                                        f"🎯 **宿題の範囲:** \n{formatted_last_hw_pages}\n\n"
                                        f"💬 **引継ぎメモ:**\n{last_note}"
                                    )
                                    
                                    assigned_p = 0
                                    assigned_hw_list = []
                                    if str(last_hw_pages).strip() and str(last_hw_pages).strip() != "-":
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
                                    is_continuous = st.checkbox("🔄 追加連続コマ（宿題チェックをスキップし、前回分を引き継ぐ）", key=f"cont_{b}_{i}")
                                    completed_p = 0
                                    
                                    if is_continuous:
                                        st.info("💡 連続コマモード：今回の宿題確認は行わず、前回の宿題をそのまま「次回の宿題指示」に引き継ぎます。")
                                        assigned_p = 0 
                                    else:
                                        if not assigned_hw_list:
                                            st.caption("※宿題指示が特殊形式のため個別表示できません。やったページ数を入力してください。")
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
                                                    
                                        st.caption(f"📊 シート保存データ ➡ 出した宿題(自動計算): **{assigned_p}** P / やった宿題: **{completed_p}** P")
                                    
                                    st.divider() 

                                    st.write("📚 **使用テキストと進捗**")
                                    usage_text_options = ["🆕 新規テキスト入力"] + text_options
                                    selected_texts = st.multiselect("使用テキスト (複数可)", usage_text_options, key=f"texts_{b}_{i}")
                                    
                                    if "🆕 新規テキスト入力" in selected_texts:
                                        new_usage_text = st.text_input("📝 新しいテキスト名を入力 (授業使用)", key=f"new_usage_text_{b}_{i}")
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
                                                
                                                col_q1, col_q2 = st.columns(2)
                                                with col_q1:
                                                    target_chap = st.number_input(f"実施した単元/回", min_value=1, value=1, step=1, key=f"q_chap_{b}_{i}_{q_idx}")
                                                with col_q2:
                                                    score = st.number_input(f"点数", min_value=0, max_value=100, value=100, step=1, key=f"q_score_{b}_{i}_{q_idx}")
                                                
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

                                    st.divider()
                                    st.write("🧠 **授業中の様子・評価**")
                                    col_eval1, col_eval2 = st.columns(2)
                                    with col_eval1:
                                        concentration = st.selectbox("集中力", ["超集中", "前向き", "疲労気味", "ムラあり", "集中できない"], index=None, placeholder="選択してください", key=f"conc_{b}_{i}")
                                    with col_eval2:
                                        reaction = st.selectbox("ミスへの反応", ["原因を分析した", "悔しがった", "放置しようとした"], index=None, placeholder="選択してください", key=f"reac_{b}_{i}")
                                    
                                    st.divider()

                                    st.write("🚀 **次回の宿題指示**")
                                    
                                    if is_continuous:
                                        selected_hw_text_str = str(last_hw_text)
                                        next_hw_pages_str = str(last_hw_pages)
                                        st.info(f"🔄 【自動引き継ぎ内容】\n\n📚 テキスト: **{selected_hw_text_str}**\n🎯 範囲: \n{next_hw_pages_str}")
                                    else:
                                        hw_text_options = ["🆕 新規テキスト入力"] + text_options
                                        selected_hw_texts = st.multiselect("次回の宿題テキスト (複数可)", hw_text_options, key=f"hw_texts_{b}_{i}")

                                        if "🆕 新規テキスト入力" in selected_hw_texts:
                                            new_text_name = st.text_input("新規テキスト名を入力", key=f"new_hw_text_{b}_{i}")
                                            if new_text_name:
                                                robust_api_call(add_new_textbook, new_text_name)
                                                selected_hw_texts.remove("🆕 新規テキスト入力")
                                                if new_text_name not in selected_hw_texts:
                                                    selected_hw_texts.append(new_text_name)
                                                cached_get_textbook_master.clear()

                                        next_hw_pages_list = []
                                        if selected_hw_texts:
                                            for t_idx, hw_text in enumerate(selected_hw_texts):
                                                st.write(f"📘 **{hw_text}** の宿題")
                                                
                                                num_ranges = st.number_input(f"【{hw_text}】から出す範囲の数 (飛び石対応)", min_value=1, max_value=5, value=1, key=f"hw_ranges_num_{b}_{i}_{t_idx}")
                                                
                                                for r_idx in range(num_ranges):
                                                    n_s_col, n_e_col = st.columns(2)
                                                    next_start = n_s_col.number_input(f"開始P ({r_idx+1})", min_value=0, value=0, key=f"n_s_{b}_{i}_{t_idx}_{r_idx}")
                                                    next_end = n_e_col.number_input(f"終了P ({r_idx+1})", min_value=0, value=0, key=f"n_e_{b}_{i}_{t_idx}_{r_idx}")
                                                    
                                                    if next_end >= next_start and next_end > 0:
                                                        next_hw_pages_list.append(f"{hw_text}: P.{next_start}〜{next_end}")
                                                        
                                            next_hw_pages_str = "\n".join(next_hw_pages_list) if next_hw_pages_list else "-"
                                            selected_hw_text_str = "、".join(selected_hw_texts)
                                        else:
                                            next_hw_pages_str = "-"
                                            selected_hw_text_str = "-"
                                            st.info("👆 テキストを選択するとページ入力欄が表示されます")
                                            
                                        st.caption(f"スプレッドシートに保存される範囲:\n{next_hw_pages_str}")

                                    st.divider()
                                    advice = st.text_area("🗣️ 授業でのアドバイス（褒めた点など）", height=80, key=f"advc_{b}_{i}")
                                    parent_msg = st.text_area("👪 保護者への連絡事項", height=80, key=f"p_msg_{b}_{i}")
                                    next_handover = st.text_area("🔄 次回への引継ぎ事項", height=80, key=f"next_h_{b}_{i}")

                                    input_data_list.append({
                                        "student_id": student_id, "name": name, "subject": subject, "text_name": text_name_str,
                                        "advanced_p": advanced_p_str, "quiz_records": quiz_records, 
                                        "w_nums_for_sheet": w_nums_for_sheet, "attendance": attendance,
                                        "late_time": late_time, "concentration": concentration or "-", "reaction": reaction or "-",
                                        "advice": advice, "parent_msg": parent_msg, "next_handover": next_handover,
                                        "assigned_p": assigned_p, "completed_p": completed_p, "advanced_p_str": advanced_p_str,
                                        "motivation_rank": motivation_rank, 
                                        "next_hw_text": selected_hw_text_str, 
                                        "next_hw_pages": next_hw_pages_str
                                    })

                                    # ==========================================
                                    # 👤 1人だけを個別に保存するボタン
                                    # ==========================================
                                    st.divider()
                                    if st.button(f"👤 {name} の記録だけを個別に保存", key=f"save_single_{b}_{i}", use_container_width=True):
                                        with st.status(f"{name} のデータを保存中...", expanded=True) as status:
                                            robust_api_call(
                                                save_to_spreadsheet,
                                                student_id=student_id, name=name, subject=subject, text_name=text_name_str,
                                                advanced_p=advanced_p_str, quiz_records=[], date=date, 
                                                teacher_name=teacher_name, class_type=class_type, attendance=attendance,
                                                class_slot=class_slot, advice=advice, parent_msg=parent_msg,
                                                next_handover=next_handover, assigned_p=assigned_p, completed_p=completed_p, 
                                                motivation_rank=motivation_rank, next_hw_text=selected_hw_text_str,
                                                next_hw_pages=next_hw_pages_str, late_time=late_time,        
                                                concentration=concentration or "-", reaction=reaction or "-"            
                                            )

                                            if quiz_records and len(quiz_records) > 0:
                                                for q in quiz_records:
                                                    robust_api_call(
                                                        save_quiz_to_dedicated_sheet,
                                                        date_str=date.strftime("%Y/%m/%d"), student_name=name, text_name=q["quiz_name"],
                                                        chapter=q["unit"], score=q["score"], w_nums="", mode="授業内"
                                                    )
                                            
                                            if attendance != "欠席（振替なし）" and "欠席" not in attendance:
                                                try:
                                                    robust_api_call(update_student_homework_rate, name, subject, assigned_p, completed_p)
                                                except Exception:
                                                    pass 
                                                
                                            status.update(label="保存完了！", state="complete", expanded=False)
                                        st.success(f"✅ {name} の記録を保存しました！")
                                        
                                        # 🚨 ここでは即座に消さず「しおり」だけ挟んでおき、一番最後でお掃除する！
                                        single_save_triggered = (b, i, name)

            st.divider()
            if len(input_data_list) == num_students:
                actual_attendees = sum(1 for data in input_data_list if "欠席" not in data["attendance"])
                actual_class_type = f"1:{actual_attendees}" if actual_attendees > 0 else class_type
                
                if actual_attendees < num_students and actual_attendees > 0:
                    st.info(f"💡 欠席者がいるため、実際の授業形態は「{actual_class_type}」として記録されます。")

                # ==========================================
                # 🚀 コマ全体の記録をまとめて保存するボタン
                # ==========================================
                if st.button(f"🚀 コマ {b+1} の全員の記録をまとめて保存する", type="primary", key=f"save_all_{b}", use_container_width=True):
                    with st.status("データを保存中...", expanded=True) as status:
                        for data in input_data_list:
                            if "欠席" in data.get("attendance", ""):
                                continue

                            robust_api_call(
                                save_to_spreadsheet,
                                student_id=data.get("student_id", ""), name=data.get("name", ""), subject=data.get("subject", ""),
                                text_name=data.get("text_name_str", data.get("text_name", "")), advanced_p=data.get("advanced_p_str", ""),
                                quiz_records=[], date=date, teacher_name=teacher_name, class_type=actual_class_type,  
                                attendance=data.get("attendance", ""), class_slot=class_slot, advice=data.get("advice", ""),
                                parent_msg=data.get("parent_msg", ""), next_handover=data.get("next_handover", ""),
                                assigned_p=data.get("assigned_p", 0), completed_p=data.get("completed_p", 0), 
                                motivation_rank=data.get("motivation_rank", ""), next_hw_text=data.get("next_hw_text", ""),
                                next_hw_pages=data.get("next_hw_pages", ""), late_time=data.get("late_time", ""),        
                                concentration=data.get("concentration", ""), reaction=data.get("reaction", "")            
                            )

                            if data.get("quiz_records") and len(data["quiz_records"]) > 0:
                                for q in data["quiz_records"]:
                                    robust_api_call(
                                        save_quiz_to_dedicated_sheet,
                                        date_str=date.strftime("%Y/%m/%d"), student_name=data["name"], text_name=q["quiz_name"],
                                        chapter=q["unit"], score=q["score"], w_nums="", mode="授業内"
                                    )
                            
                            if data["attendance"] != "欠席（振替なし）" and "欠席" not in data["attendance"]:
                                try:
                                    robust_api_call(update_student_homework_rate, data["name"], data["subject"], data["assigned_p"], data["completed_p"])
                                except Exception:
                                    pass 
                        
                        status.update(label="保存完了！", state="complete", expanded=False)

                    st.success(f"✅ コマ {b+1}（{actual_attendees}名）の記録を保存しました！")
                    
                    # しおりを挟んで一番最後でお掃除する
                    all_save_triggered = (b, num_students)


    # ==========================================
    # 🧹 一番最後での遅延お掃除処理（他のタブを巻き添えにしない魔法）
    # ==========================================
    
    # 👤 1人だけ保存した場合のお掃除
    if single_save_triggered:
        b_idx, i_idx, saved_name = single_save_triggered
        target_prefixes = [
            "sel_student", "new_name", "att", "late", "sub", "cont", 
            "done_start", "done_end", "texts", "new_usage_text", "adv_start", 
            "adv_end", "num_q", "q_name", "q_chap", "q_score", "w", 
            "conc", "reac", "hw_texts", "new_hw_text", "hw_ranges_num", 
            "n_s", "n_e", "advc", "p_msg", "next_h", "d_s", "d_e"
        ]
        # 保存したコマの、保存した生徒のキーだけをスナイプ削除
        for key in list(st.session_state.keys()):
            for p in target_prefixes:
                if key == f"{p}_{b_idx}_{i_idx}" or key.startswith(f"{p}_{b_idx}_{i_idx}_"):
                    del st.session_state[key]
                    break
        if saved_name:
            for key in list(st.session_state.keys()):
                if key.startswith(f"prev_data_{saved_name}_"):
                    del st.session_state[key]
                    
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()

    # 🚀 コマ全員まとめて保存した場合のお掃除
    if all_save_triggered:
        b_idx, students_count = all_save_triggered
        
        # 1. そのコマの共通設定（日付・講師など）を削除
        for k in ["class_date", "sb_teacher", "class_type", "sb_class_slot"]:
            if f"{k}_{b_idx}" in st.session_state:
                del st.session_state[f"{k}_{b_idx}"]

        # 2. そのコマの全生徒の入力欄を削除
        target_prefixes = [
            "sel_student", "new_name", "att", "late", "sub", "cont", 
            "done_start", "done_end", "texts", "new_usage_text", "adv_start", 
            "adv_end", "num_q", "q_name", "q_chap", "q_score", "w", 
            "conc", "reac", "hw_texts", "new_hw_text", "hw_ranges_num", 
            "n_s", "n_e", "advc", "p_msg", "next_h", "d_s", "d_e"
        ]
        for i_idx in range(students_count):
            for key in list(st.session_state.keys()):
                for p in target_prefixes:
                    if key == f"{p}_{b_idx}_{i_idx}" or key.startswith(f"{p}_{b_idx}_{i_idx}_"):
                        del st.session_state[key]
                        break
        
        if "draft_data" in st.session_state:
            del st.session_state["draft_data"]
            
        st.cache_data.clear()
        time.sleep(1.5)
        st.rerun()