import streamlit as st
import datetime
import pandas as pd
import time

from utils.g_sheets import (
    get_all_logs,
    load_quiz_records, 
    load_school_homework_data,
    get_sent_list,      
    update_sent_flag,
    save_parent_reply,
    get_student_master,
    get_all_teacher_names
)
from utils.g_drive import get_or_create_student_folder
from utils.api_guard import robust_api_call

@st.cache_data(ttl=60, show_spinner=False)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60, show_spinner=False)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60, show_spinner=False)
def cached_load_hw_records():
    return robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_teacher_names():
    return robust_api_call(get_all_teacher_names, fallback_value=[])


def render_line_report_page():
    # 🌟 変更ポイント：ヘッダーの横にリロードボタンを配置
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("📱 LINE用 授業報告レポート管理")
    with col_r:
        if st.button("🔄 データを更新", use_container_width=True):
            st.cache_data.clear() # キャッシュを強制クリア
            st.rerun()            # 画面を再読み込み
    
    user_role = st.session_state.get('role', '')
    
    can_use_report = user_role in ['admin', 'owner', 'AM', 'head_teacher']
    can_use_reply = user_role in ['admin', 'owner', 'AM']

    if not can_use_report and not can_use_reply:
        st.error("🔒 このページへのアクセス権限がありません。管理者または教室長（社員）のみ利用可能です。")
        st.stop()

    if can_use_reply:
        main_tab1, main_tab2 = st.tabs(["📱 LINEレポート一括生成", "💬 保護者返信・ファン化度記録"])
        report_container = main_tab1
        reply_container = main_tab2
    else:
        report_container = st.container()
        reply_container = None

    # ==========================================
    # エリア1：レポート一括生成
    # ==========================================
    with report_container:
        st.write("授業日を選択するだけで、**校舎ごと**に全生徒のレポートを自動生成します✨")
        
        selected_date = st.date_input("📅 授業日を選択", datetime.date.today(), key="report_target_date")
        date_str = selected_date.strftime("%Y/%m/%d")

        st.divider()

        with st.spinner(f"{date_str} の全データを解析中..."):
            df_all_logs = cached_get_all_logs()
            df_all_quizzes = cached_load_quiz_records()
            df_hw = cached_load_hw_records()

            if df_all_logs.empty or "APIエラー発生" in df_all_logs.columns:
                st.error("授業記録データの取得に失敗しました。")
                st.stop()

            df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
            target_date = pd.to_datetime(selected_date).date()
            daily_logs = df_all_logs[df_all_logs['日時'].dt.date == target_date]

        if daily_logs.empty:
            st.info(f"📅 {date_str} の授業記録はまだありません。")
        else:
            sent_id_list = robust_api_call(get_sent_list, date_str, fallback_value=[])
            id_col = '生徒ID' if '生徒ID' in daily_logs.columns else None
            name_col = '名前' if '名前' in daily_logs.columns else '生徒名'

            target_students = daily_logs[[id_col, name_col]].drop_duplicates().to_dict('records')

            if can_use_report:
                missing_url_students = []
                for s in target_students:
                    s_name = s.get(name_col, "不明")
                    has_quiz = False
                    if not df_all_quizzes.empty and "APIエラー発生" not in df_all_quizzes.columns:
                        df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
                        student_quizzes = df_all_quizzes[(df_all_quizzes['名前'] == s_name) & (df_all_quizzes['日時'].dt.date == target_date)]
                        if not student_quizzes.empty:
                            has_quiz = True
                    if not has_quiz:
                        missing_url_students.append(s_name)
                if missing_url_students:
                    st.error(f"🚨 **【答案確認URL 未添付アラート】** 以下の生徒は小テスト記録がないため、報告書に「答案確認URL」が表示されていません。\n\n**{', '.join(missing_url_students)}**")

            data_buckets = {"田端新町校": [], "東十条駅前校": [], "体験授業": [], "その他": []}
            for s in target_students:
                s_id = str(s.get(id_col, "")).lower()
                if s_id == "trial": data_buckets["体験授業"].append(s)
                elif s_id.startswith('t'): data_buckets["田端新町校"].append(s)
                elif s_id.startswith('h'): data_buckets["東十条駅前校"].append(s)
                else: data_buckets["その他"].append(s)

            display_buckets = {k: v for k, v in data_buckets.items() if len(v) > 0 or k != "その他"}
            tabs = st.tabs([f"🏫 {k} ({len(v)}名)" for k, v in display_buckets.items()])

            for t_idx, (bucket_name, students) in enumerate(display_buckets.items()):
                with tabs[t_idx]:
                    if not students:
                        st.caption("対象の生徒はいません。")
                        continue

                    for s_idx, student_info in enumerate(students):
                        student_id = student_info.get(id_col, "未設定")
                        student_name = student_info.get(name_col, "不明")

                        student_classes = daily_logs[daily_logs[id_col].astype(str) == str(student_id)]
                        class_sections = []; advice_sections = []; hw_sections = []; parent_msg_sections = []; bring_sections = []

                        for _, row in student_classes.iterrows():
                            teacher = row.get("担当講師", "（未入力）")
                            subject = row.get("科目", "（未入力）")
                            period = row.get("授業コマ", "（未入力）")
                            
                            text_name = str(row.get("テキスト", "")).strip()
                            if text_name == "nan": text_name = ""
                            end_page = str(row.get("終了ページ", "")).strip()
                            if end_page == "nan": end_page = ""
                            
                            if end_page:
                                progress = "\n " + end_page.replace("\n", "\n ") if "\n" in end_page else end_page
                            elif text_name:
                                progress = f"{text_name}"
                            else:
                                progress = "（未入力）"
                            
                            concentration = row.get("集中力", "")
                            reaction = row.get("ミスへの反応", "")
                            attitude = f"集中力: {concentration} / ミスへの反応: {reaction}" if concentration or reaction else "（未入力）"

                            hw_reason = str(row.get("未達成の理由", "")).strip()
                            hw_fix = str(row.get("本日の修正策", "")).strip()
                            hw_status_line = f"\n・宿題状況：未達成（理由: {hw_reason.replace('その他: ','')} ➡ 対策: {hw_fix.replace('その他: ','')}）" if (hw_reason and hw_reason != "nan") or (hw_fix and hw_fix != "nan") else ""
                            
                            advice = str(row.get("授業アドバイス", row.get("アドバイス", ""))).strip()
                            parent_msg = str(row.get("保護者への連絡", "")).strip()
                            
                            bring = str(row.get("次回の持ち物", "")).strip()
                            if bring and bring != "nan": bring_sections.append(f"・{bring}（{subject}）")
                            
                            next_hw_pages = str(row.get("次回の宿題ページ数", "")).strip()
                            if next_hw_pages == "nan" or next_hw_pages == "-": next_hw_pages = ""

                            hw_content = ""
                            if next_hw_pages: hw_content = f"{next_hw_pages}"

                            prefix = "🎨 【体験内容】" if bucket_name == "体験授業" else "📅 【授業内容】"
                            class_text = f"{prefix}（{period} / {subject} / 担当：{teacher}）\n・進捗：{progress}\n・様子：{attitude}{hw_status_line}"
                            class_sections.append(class_text)

                            if advice and advice != "nan": advice_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{advice}")
                            if parent_msg and parent_msg != "nan": parent_msg_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{parent_msg}")
                            if hw_content: hw_sections.append(f"《{subject if bucket_name != '体験授業' else ''} {teacher}先生より》\n{hw_content}")

                        classes_text = "\n\n".join(class_sections)
                        bring_text = f"🎒 【次回の持ち物】\n" + "\n".join(bring_sections) + "\n\n" if bring_sections else ""
                        hw_text = f"📘 【次回の宿題】\n" + "\n\n".join(hw_sections) + "\n\n" if hw_sections else ""

                        quiz_text = "小テストは実施していません"
                        drive_url_line = ""
                        if not df_all_quizzes.empty:
                            df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
                            student_quizzes = df_all_quizzes[(df_all_quizzes['名前'] == student_name) & (df_all_quizzes['日時'].dt.date == target_date)]
                            if not student_quizzes.empty:
                                quiz_results = [f"【{row.get('テキスト', '不明')} {row.get('単元', '不明')}】: {row.get('点数', '不明')}点" for _, row in student_quizzes.iterrows()]
                                quiz_text = "\n・".join(quiz_results)
                                folder_id = robust_api_call(get_or_create_student_folder, student_id, student_name, fallback_value=None)
                                if folder_id:
                                    drive_url_line = f"📂 【本日の答案確認URL】\nhttps://drive.google.com/drive/folders/{folder_id}\n\n"

                        if bucket_name == "体験授業":
                            advices_block = f"🗣️ 【本日の輝いていた点】\n" + "\n\n".join(advice_sections) + "\n\n" if advice_sections else ""
                            msgs_block = f"📢 【今後の課題・ご提案】\n" + "\n\n".join(parent_msg_sections) + "\n\n" if parent_msg_sections else ""
                            line_message = f"保護者様\n\n本日は {student_name} さんの「体験授業」にお越しいただき、ありがとうございました！\n\n{classes_text}\n\n💯 【小テスト結果】\n・{quiz_text}\n\n{drive_url_line}{bring_text}{advices_block}{msgs_block}引き続きよろしくお願いいたします。\n槌屋"
                        else:
                            advices_block = f"🗣️ 【アドバイス(褒めた点など)】\n" + "\n\n".join(advice_sections) + "\n\n" if advice_sections else ""
                            msgs_block = f"📢 【ご連絡事項】\n" + "\n\n".join(parent_msg_sections) + "\n\n" if parent_msg_sections else ""
                            line_message = f"保護者様\n\nお世話になっております。本日の {student_name} さんの授業報告です。\n\n{classes_text}\n\n💯 【小テスト結果】\n・{quiz_text}\n\n{drive_url_line}{bring_text}{hw_text}{advices_block}{msgs_block}よろしくお願いいたします。\n槌屋"

                        checkbox_key = f"sent_{date_str}_{student_id}"
                        is_already_sent = str(student_id) in sent_id_list
                        
                        c_check, c_exp = st.columns([1, 9])
                        check_val = c_check.checkbox("送済", value=is_already_sent, key=checkbox_key)
                        if check_val != is_already_sent:
                            robust_api_call(update_sent_flag, date_str, student_id, check_val)
                            st.rerun()

                        label_suffix = " ［✅ 送信完了］" if check_val else ""
                        with c_exp:
                            with st.expander(f"👤 {student_name} {label_suffix}", expanded=False):
                                st.code(line_message, language="text")
                                st.caption("👆 コピーしてLINEへペースト！")

    # ==========================================
    # エリア2：保護者返信・ファン化度記録
    # ==========================================
    if reply_container is not None:
        with reply_container:
            st.write("LINE報告に対する保護者様からのリアクションや返信を記録し、信頼関係の見える化（ファン化分析）に活用します✨")
            
            df_students = cached_get_student_master()
            teacher_names = cached_get_teacher_names()
            
            if df_students.empty:
                st.warning("生徒データが読み込めません。")
            else:
                student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
                
                selected_student = st.selectbox("👤 返信のあった生徒を選択してください", student_options, index=None, placeholder="-- 生徒を選択 --", key="parent_reply_student_select")
                
                if selected_student:
                    student_id = selected_student.split(" - ")[0]
                    student_name = selected_student.split(" - ")[1]
                    
                    with st.form(key=f"parent_reply_form"):
                        st.markdown(f"### 💬 {student_name} さんの保護者リアクション登録")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            target_date = st.date_input("📅 対象の授業日（報告書を送った日）", datetime.date.today())
                        with c2:
                            teacher_name = st.selectbox("👨‍🏫 報告書を作成した担当講師", teacher_names, index=None, placeholder="-- 講師を選択 --")
                            
                        reaction_type = st.selectbox(
                            "🤝 保護者のリアクション・ファン化度評価",
                            [
                                "🔥 大絶賛・大感謝（超ファン化・講習の提案やお知らせに即合意レベル）",
                                "🟢 好意的・納得（信頼構築・塾への指示通りに家庭が動く状態）",
                                "🟡 質問・相談あり（家庭との対話要フォロー・要社員共有）",
                                "🚨 悪印象・不満あり（至急のフォロー・面談要レベル）"
                            ],
                            index=1
                        )
                        
                        reply_text = st.text_area(
                            "📝 返信内容・特記事項（メモ）", 
                            placeholder="実際の文面や、相談された内容の要約を入力してください。", 
                            height=120
                        )
                        
                        submit_reply = st.form_submit_button("🚀 保護者の返信記録をスプレッドシートへ保存する", use_container_width=True)
                        
                        if submit_reply:
                            if not teacher_name:
                                st.error("⚠️ 担当講師を選択してください。")
                            else:
                                with st.spinner("データを安全に書き込み中..."):
                                    success = robust_api_call(
                                        save_parent_reply,
                                        date_str=target_date.strftime("%Y/%m/%d"),
                                        student_id=student_id,
                                        student_name=student_name,
                                        teacher_name=teacher_name, 
                                        reaction_type=reaction_type,
                                        reply_text=reply_text,
                                        fallback_value=False
                                    )
                                    if success:
                                        st.success(f"✅ {student_name} さんの保護者返信を正常に記録しました！")
                                        time.sleep(1.5)
                                        st.rerun()
                                    else:
                                        st.error("❌ スプレッドシートへの保存に失敗しました。")