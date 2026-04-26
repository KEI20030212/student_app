import streamlit as st
import datetime
import time
import re

from utils.g_sheets import (
    get_all_student_names, 
    get_all_teacher_names,
    save_to_spreadsheet, 
    get_last_page_from_sheet, 
    update_student_homework_rate,
    save_self_study_record,
    get_last_handover,
    get_last_homework_info,  
    add_new_textbook,        
    get_textbook_master,
    save_quiz_to_dedicated_sheet
)
from utils.calc_logic import (
    calculate_hw_rate, 
    calculate_quiz_points, 
    calculate_motivation_rank
)

def render_multi_input_page(textbook_master):
    st.header("📝 授業・自習記録の入力")

    record_type = st.radio("✍️ 記録の種類を選択してください", ["📖 授業", "📝 自習"], horizontal=True)
    st.divider()

    if "cached_student_names" not in st.session_state:
        st.session_state["cached_student_names"] = get_all_student_names()
    student_names = st.session_state["cached_student_names"]

    if "cached_teacher_names" not in st.session_state:
        st.session_state["cached_teacher_names"] = get_all_teacher_names()
    teacher_names = st.session_state["cached_teacher_names"]

    if "cached_text_options" not in st.session_state:
        st.session_state["cached_text_options"] = list(get_textbook_master().keys())
    text_options = st.session_state["cached_text_options"]


    if record_type == "📖 授業":
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
            date = c1.date_input("授業日", datetime.date.today())
            
            # 💡 改善: 「--選択--」を排除！ index=None と placeholder を使って美しく！
            teacher_name = c2.selectbox(
                "👨‍🏫 担当講師", 
                teacher_names, 
                index=None, 
                placeholder="講師を選択",
                key="sb_teacher"
            )
            
            class_type = c3.radio("👥 授業形態", ["1:1", "1:2", "1:3"], horizontal=True)
            
            time_slots = [
                "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
                "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
            ]
            
            # 💡 改善: ここも「--選択--」を排除！
            class_slot = c4.selectbox(
                "⏰ 授業コマ", 
                time_slots, 
                index=None,
                placeholder="コマを選択",
                key="sb_class_slot"
            )

        # 講師かコマが未選択なら、入力をブロック
        if not teacher_name or not class_slot:
            st.info("👆 まずは「担当講師」と「授業コマ」を選択してください。")
        else:
            num_students = int(class_type.split(":")[1])
            options = ["🆕 新規登録"] + student_names
            st.divider()
            cols = st.columns(num_students)
            input_data_list = []

            for i in range(num_students):
                with cols[i]:
                    with st.container(border=True):
                        # 💡 改善: 生徒名も「--選択--」を排除！
                        name = st.selectbox("生徒名", options, index=None, placeholder="生徒を選択", key=f"name_{i}")
                        if name == "🆕 新規登録": 
                            name = st.text_input("新しい生徒の名前", key=f"new_name_{i}")

                        if name:
                            attendance = st.selectbox("📅 出欠状況", ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"], key=f"att_{i}")
                            
                            # 💡 改善: 遅刻時間の入力欄を追加
                            late_time = st.number_input("⏰ 遅刻時間 (分)", min_value=0, value=0, step=5, key=f"late_{i}")

                            if "欠席" in attendance:
                                st.warning("欠席のため、進捗・テスト入力はスキップされます。")
                                input_data_list.append({
                                    "name": name, "subject": "-", "text_name": "-", "advanced_p": "-", 
                                    "quiz_records": [], "w_nums_for_sheet": "", "attendance": attendance,
                                    "late_time": late_time, "concentration": "-", "reaction": "-",
                                    "advice": "-", "parent_msg": "-", "next_handover": "-",
                                    "assigned_p": 0, "completed_p": 0, "motivation_rank": 0, 
                                    "next_hw_text": "-", "next_hw_pages": "-"
                                })
                            else:
                                # 💡 改善: 科目の選択。「--選択--」を排除。
                                subject = st.selectbox("科目", ["英語", "数学", "国語", "理科", "社会"], index=None, placeholder="科目を選択", key=f"sub_{i}")
                                
                                # 💡 改善: 科目が選ばれるまで下を隠す（ブロックする）！
                                if not subject:
                                    st.info("👆 科目を選択すると詳細入力が開きます")
                                else:
                                    cache_key = f"prev_data_{name}_{subject}"
                                    if cache_key not in st.session_state:
                                        with st.spinner("☁️ 過去のデータを読み込み中..."):
                                            st.session_state[cache_key] = {
                                                "note": get_last_handover(name, subject),
                                                "hw_info": get_last_homework_info(name, subject),
                                                "page": get_last_page_from_sheet(name)
                                            }
                                    
                                    cached_data = st.session_state[cache_key]
                                    last_note = cached_data["note"]
                                    last_hw_text, last_hw_pages = cached_data["hw_info"]
                                    last_page = cached_data["page"]
                                    
                                    # 数字以外（"プリント"等）が入っている場合の安全対策
                                    last_page_num = int(last_page) if str(last_page).isdigit() else 0

                                    st.info(f"💡 **【前回 ({subject}) の引継ぎ事項】**\n\n{last_note}")

                                    # 🌟 さらに改善: 複数テキスト対応＆個別の進捗入力 ＋ 新規テキスト入力機能！
                                    st.write("📚 **使用テキストと進捗**")
                                    usage_text_options = ["🆕 新規テキスト入力"] + text_options
                                    selected_texts = st.multiselect("使用テキスト (複数可)", usage_text_options, key=f"texts_{i}")
                                    
                                    # 🆕 「新規テキスト入力」が選ばれた場合の処理
                                    if "🆕 新規テキスト入力" in selected_texts:
                                        new_usage_text = st.text_input("📝 新しいテキスト名を入力 (授業使用)", key=f"new_usage_text_{i}")
                                        if new_usage_text:
                                            # マスターに登録
                                            add_new_textbook(new_usage_text)
                                            # リストから "🆕 新規テキスト入力" を外し、新しいテキスト名を追加
                                            selected_texts.remove("🆕 新規テキスト入力")
                                            if new_usage_text not in selected_texts:
                                                selected_texts.append(new_usage_text)
                                            
                                            # キャッシュをクリアして、他の入力欄や次回以降の選択肢に反映させる
                                            if "cached_text_options" in st.session_state:
                                                del st.session_state["cached_text_options"]

                                    advanced_p_list = []
                                    if selected_texts and "🆕 新規テキスト入力" not in selected_texts:
                                        text_name_str = "、".join(selected_texts)
                                        for t_idx, text_name in enumerate(selected_texts):
                                            st.caption(f"📘 {text_name} の進捗")
                                            col_adv1, col_adv2 = st.columns(2)
                                            with col_adv1:
                                                adv_start = st.number_input(f"開始P", min_value=0, value=last_page_num, key=f"adv_start_{i}_{t_idx}")
                                            with col_adv2:
                                                adv_end = st.number_input(f"終了P", min_value=0, value=last_page_num, key=f"adv_end_{i}_{t_idx}")
                                            
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
                                    
                                    # 🌟 さらに改善: 小テストを複数回＆それぞれテキスト選択
                                    num_quizzes = st.number_input("💯 小テスト実施回数", min_value=0, max_value=5, value=0, step=1, key=f"num_q_{i}")
                                    quiz_records = []
                                    w_nums_for_sheet_list = []
                                    current_quiz_pts = 0 
                                    
                                    if num_quizzes > 0:
                                        for q_idx in range(num_quizzes):
                                            with st.container(border=True):
                                                st.write(f"**【小テスト {q_idx + 1}】**")
                                                q_name = st.selectbox(f"テストの種類", text_options, index=None, placeholder="テキストを選択", key=f"q_name_{i}_{q_idx}")
                                                target_chap = st.number_input(f"実施した章/範囲", min_value=1, value=1, step=1, key=f"q_chap_{i}_{q_idx}")
                                                w_nums = st.text_input(f"ミス問題番号", key=f"w_{i}_{q_idx}")
                                                
                                                score = 100 if not w_nums else max(0, 100 - (len(w_nums.split(",")) * 10))
                                                quiz_records.append({
                                                    "quiz_name": q_name or "不明",  # 👈 選んだテキスト名を記録！
                                                    "unit": target_chap, 
                                                    "score": score
                                                })
                                                if w_nums:
                                                    w_nums_for_sheet_list.append(w_nums)
                                                current_quiz_pts += calculate_quiz_points(score)
                                    
                                    w_nums_for_sheet = ",".join(w_nums_for_sheet_list)

                                    # 💡 改善: 宿題のデータがない（変数が存在しない）場合は 0 として扱う安全対策
                                    safe_hw_rate = current_hw_rate if 'current_hw_rate' in locals() else 0
                                    motivation_rank = calculate_motivation_rank(safe_hw_rate, current_quiz_pts)

                                    st.divider()
                                    
                                    # 💡 改善: 集中力とミスへの反応の評価を追加！
                                    st.write("🧠 **授業中の様子・評価**")
                                    col_eval1, col_eval2 = st.columns(2)
                                    with col_eval1:
                                        concentration = st.selectbox("集中力", ["超集中", "疲労気味", "ムラあり", "集中できない"], index=None, placeholder="選択してください", key=f"conc_{i}")
                                    with col_eval2:
                                        reaction = st.selectbox("ミスへの反応", ["原因を分析した", "悔しがった", "放置しようとした"], index=None, placeholder="選択してください", key=f"reac_{i}")
                                    
                                    st.divider()

                                    st.write("🚀 **次回の宿題指示**")
                                    hw_text_options = ["🆕 新規テキスト入力"] + text_options
                                    selected_hw_text = st.selectbox("次回の宿題テキスト", hw_text_options, index=None, placeholder="テキストを選択", key=f"hw_text_{i}")

                                    if selected_hw_text == "🆕 新規テキスト入力":
                                        new_text_name = st.text_input("新規テキスト名を入力", key=f"new_hw_text_{i}")
                                        if new_text_name:
                                            add_new_textbook(new_text_name)
                                            selected_hw_text = new_text_name
                                            if "cached_text_options" in st.session_state:
                                                del st.session_state["cached_text_options"]

                                    st.write("宿題の範囲")
                                    n_s_col, n_e_col = st.columns(2)
                                    next_start = n_s_col.number_input("次 開始P", min_value=0, value=0, key=f"n_start_{i}")
                                    next_end = n_e_col.number_input("次 終了P", min_value=0, value=0, key=f"n_end_{i}")
                                    
                                    if next_end >= next_start and next_end > 0:
                                        next_hw_pages_str = f"P.{next_start}〜{next_end}"
                                    else:
                                        next_hw_pages_str = "-"
                                        
                                    st.caption(f"スプレッドシートに保存される範囲: {next_hw_pages_str}")

                                    st.divider()
                                    advice = st.text_area("🗣️ 授業でのアドバイス（褒めた点など）", height=80, key=f"advc_{i}")
                                    parent_msg = st.text_area("👪 保護者への連絡事項", height=80, key=f"p_msg_{i}")
                                    next_handover = st.text_area("🔄 次回への引継ぎ事項", height=80, key=f"next_h_{i}")

                                    input_data_list.append({
                                        "name": name, "subject": subject, "text_name": text_name_str,
                                        "advanced_p": advanced_p_str, "quiz_records": quiz_records, 
                                        "w_nums_for_sheet": w_nums_for_sheet, "attendance": attendance,
                                        "late_time": late_time, "concentration": concentration or "-", "reaction": reaction or "-",
                                        "advice": advice, "parent_msg": parent_msg, "next_handover": next_handover,
                                        "assigned_p": 0, "completed_p": 0, "advanced_p_str": advanced_p_str,
                                        "motivation_rank": motivation_rank, 
                                        "next_hw_text": selected_hw_text or "-", 
                                        "next_hw_pages": next_hw_pages_str
                                    })

            st.divider()
            if len(input_data_list) == num_students:

                if st.button("🚀 全員の記録をまとめて保存する", type="primary", use_container_width=True):
                    with st.status("データを保存中...", expanded=True) as status:
                        for data in input_data_list:
                            
                            # 1. いつも通りの授業記録を保存
                            save_to_spreadsheet(
                                name=data.get("name", ""),
                                subject=data.get("subject", ""),
                                text_name=data.get("text_name_str", data.get("text_name", "")), # 👈 複数テキストの名前に対応
                                advanced_p=data.get("advanced_p_str", ""),                      # 👈 「P.10〜20」などの新しい進捗に対応
                                quiz_records=[],
                                date=date, 
                                teacher_name=teacher_name,
                                class_type=class_type,
                                attendance=data.get("attendance", ""),
                                class_slot=class_slot,
                                advice=data.get("advice", ""),
                                parent_msg=data.get("parent_msg", ""),
                                next_handover=data.get("next_handover", ""),
                                assigned_p=0,  # 👈 使わなくなった古いデータなのでダミーの0を渡す
                                completed_p=0, # 👈 使わなくなった古いデータなのでダミーの0を渡す
                                motivation_rank=data.get("motivation_rank", ""),
                                next_hw_text=data.get("next_hw_text", ""),
                                next_hw_pages=data.get("next_hw_pages", ""),
                                late_time=data.get("late_time", ""),        # 🌟新規パラメータ
                                concentration=data.get("concentration", ""),# 🌟新規パラメータ
                                reaction=data.get("reaction", "")           # 🌟新規パラメータ
                            )

                            # 2. 小テストの専用シート保存
                            if data.get("quiz_records") and len(data["quiz_records"]) > 0:
                                for q in data["quiz_records"]:
                                    save_quiz_to_dedicated_sheet(
                                        date_str=date.strftime("%Y/%m/%d"),
                                        student_name=data["name"],
                                        text_name=q["quiz_name"],
                                        chapter=q["unit"],
                                        score=q["score"],
                                        w_nums=data["w_nums_for_sheet"],
                                        mode="授業内"
                                    )
                            
                            if data["attendance"] != "欠席（振替なし）" and "欠席" not in data["attendance"]:
                                try:
                                    update_student_homework_rate(
                                        data["name"], data["subject"], data["assigned_p"], data["completed_p"]
                                    )
                                except Exception:
                                    pass 
                        
                        status.update(label="保存完了！", state="complete", expanded=False)

                    st.success(f"✅ {num_students}名全員の記録を保存しました！")
                    
                    st.cache_data.clear()
                    time.sleep(2)

                    if "sb_class_slot" in st.session_state:
                        del st.session_state["sb_class_slot"]

                    for i in range(num_students):
                        keys_to_reset = [
                            f"name_{i}", f"att_{i}", f"late_{i}", f"sub_{i}", f"texts_{i}", 
                            f"done_start_{i}", f"done_end_{i}", f"adv_start_{i}", f"adv_end_{i}", 
                            f"num_q_{i}", f"conc_{i}", f"reac_{i}",
                            f"hw_text_{i}", f"n_start_{i}", f"n_end_{i}",
                            f"advc_{i}", f"p_msg_{i}", f"next_h_{i}",
                            f"new_usage_text_{i}" # 👈 忘れずに新規入力用のキーもリセット！
                        ]
                        # 動的に増える小テストのキーもリセット
                        for q_idx in range(5):
                            keys_to_reset.extend([f"q_chap_{i}_{q_idx}", f"w_{i}_{q_idx}"])

                        for k in keys_to_reset:
                            if k in st.session_state:
                                del st.session_state[k]
                    
                    for key in list(st.session_state.keys()):
                        if key.startswith("prev_data_"):
                            del st.session_state[key]

                    st.rerun() 
    # ==========================================
    # 📝 自習記録の入力画面（複数日・休憩・ポイント計算対応＆絶対エラー防護版）
    # ==========================================
    elif record_type == "📝 自習":
        with st.container(border=True):
            st.write("📚 **自習記録の入力（一括登録モード）**")
            
            ss_options = ["🆕 新規登録"] + student_names
            ss_name = st.selectbox("👤 生徒を選択", ss_options, index=None, placeholder="生徒を選択", key="ss_name")
            
            if ss_name == "🆕 新規登録": 
                ss_name = st.text_input("新しい生徒の名前", key="ss_new_name")
            
            if ss_name:
                num_days = st.number_input("🗓️ 登録する日数", min_value=1, max_value=14, value=1, key="ss_num_days")
                st.divider()
                
                ss_records = []
                total_earned_points = 0
                
                for d in range(int(num_days)):
                    st.write(f"**【 {d+1}日目の記録 】**")
                    col_d, col_s, col_e, col_b = st.columns([1.5, 1.2, 1.2, 1])
                    
                    default_date = datetime.date.today() - datetime.timedelta(days=d)
                    ss_date = col_d.date_input("📅 日付", default_date, key=f"d_{d}")
                    
                    # 💡案A: 開始・終了時間の入力
                    s_time = col_s.time_input("🛫 開始", datetime.time(17, 0), key=f"s_{d}")
                    e_time = col_e.time_input("🛬 終了", datetime.time(19, 0), key=f"e_{d}")
                    b_min = col_b.number_input("☕ 休憩(分)", min_value=0, value=0, step=5, key=f"b_{d}")
                    
                    # 時間計算ロジック
                    start_dt = datetime.datetime.combine(ss_date, s_time)
                    end_dt = datetime.datetime.combine(ss_date, e_time)
                    diff_min = (end_dt - start_dt).seconds // 60
                    if end_dt < start_dt: # 日を跨ぐ場合（念のため）
                        diff_min = 0
                        
                    actual_min = max(0, diff_min - b_min)
                    pts = int(actual_min // 30) # 30分につき1pt
                    total_earned_points += pts
                    
                    st.caption(f"⏱️ 滞在: {diff_min}分 ／ 🔥 実質勉強時間: **{actual_min}分** （獲得: {pts}pt）")
                    ss_memo = st.text_area("📖 学習内容（テキスト名など）", height=70, key=f"m_{d}")
                    
                    ss_records.append({
                        "date": ss_date, "start": s_time, "end": e_time, 
                        "break": b_min, "actual": actual_min, "content": ss_memo, "pts": pts
                    })
                    st.divider()
                
                if st.button(f"💾 {num_days}日分のデータを安全に保存する", type="primary", use_container_width=True):
                    with st.status("Googleスプレッドシートに送信中...", expanded=True) as status:
                        success_count = 0
                        for idx, rec in enumerate(ss_records):
                            # 保存関数の呼び出し（引数を案Aに合わせる）
                            ok, msg = save_self_study_record(
                                rec["date"], ss_name, rec["start"], rec["end"], 
                                rec["break"], rec["actual"], rec["content"], rec["pts"]
                            )
                            if ok:
                                success_count += 1
                                # 🛡️ APIエラー対策: 1件ごとに2秒待機してGoogleを怒らせないようにする
                                if idx < len(ss_records) - 1:
                                    time.sleep(2)
                            else:
                                st.error(f"❌ {idx+1}件目でエラー: {msg}")
                                break # 1つ失敗したら止める
                                
                        if success_count == len(ss_records):
                            status.update(label="すべて正常に保存されました！", state="complete", expanded=False)
                            st.success(f"✅ {ss_name}さんの{success_count}日分の記録を保存！ 合計 {total_earned_points}pt 獲得！")
                            st.balloons()
                            time.sleep(2)
                            # リセット処理
                            for k in list(st.session_state.keys()):
                                if k.startswith(("d_","s_","e_","b_","m_","ss_")): del st.session_state[k]
                            st.rerun()