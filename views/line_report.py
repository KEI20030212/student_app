import streamlit as st
import datetime
import pandas as pd

from utils.g_sheets import (
    get_all_logs,
    load_quiz_records, 
    load_school_homework_data 
)
from utils.api_guard import robust_api_call

# 🌟 全データを一括取得するキャッシュ関数群
@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_load_hw_records():
    return robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())

def render_line_report_page():
    st.header("📱 LINE用 授業報告レポート一括生成")
    st.write("授業日を選択するだけで、**その日に授業があった全生徒のレポート**を自動生成します✨")

    # 1. 🌟 生徒選択をなくし、日付選択のみの超シンプルUIに！
    selected_date = st.date_input("📅 授業日を選択", datetime.date.today())

    st.divider()

    with st.spinner(f"{selected_date.strftime('%Y/%m/%d')} の全レポートを作成中...（超高速🚀）"):
        date_str = selected_date.strftime("%Y/%m/%d")

        # 3つのデータベースを1回ずつだけ読み込む
        df_all_logs = cached_get_all_logs()
        df_all_quizzes = cached_load_quiz_records()
        df_hw = cached_load_hw_records()

        if df_all_logs.empty or "APIエラー発生" in df_all_logs.columns:
            st.error("授業記録データの取得に失敗しました。")
            st.stop()

        # --- 🌟 その日に授業があった生徒を抽出 ---
        df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
        target_date = pd.to_datetime(selected_date).date()
        daily_logs = df_all_logs[df_all_logs['日時'].dt.date == target_date]

        if daily_logs.empty:
            st.info(f"📅 {date_str} の授業記録はまだありません。")
            st.stop()

        # IDと名前の列を特定
        id_col = '生徒ID' if '生徒ID' in daily_logs.columns else None
        name_col = '名前' if '名前' in daily_logs.columns else '生徒名'

        # その日に授業があった「生徒のリスト（重複なし）」を一瞬で作る
        if id_col:
            target_students = daily_logs[[id_col, name_col]].drop_duplicates().to_dict('records')
        else:
            target_students = daily_logs[[name_col]].drop_duplicates().to_dict('records')

        st.success(f"🎉 {len(target_students)}名分のレポートを生成しました！各アコーディオンを開いてコピーしてください。")

        # --- 🌟 生徒ごとにループしてレポートを作成 ---
        for student_info in target_students:
            student_id = student_info.get(id_col, "未設定") if id_col else "未設定"
            student_name = student_info.get(name_col, "不明")

            # ==========================================
            # ① その生徒の「授業記録」の抽出
            # ==========================================
            if student_id != "未設定":
                student_classes = daily_logs[daily_logs[id_col].astype(str) == str(student_id)]
            else:
                student_classes = daily_logs[daily_logs[name_col] == student_name]

            class_sections = []
            advice_sections = []
            parent_msg_sections = []

            for _, row in student_classes.iterrows():
                teacher = row.get("担当講師", "（未入力）")
                subject = row.get("科目", "（未入力）")
                period = row.get("授業コマ", "（未入力）")
                
                text_name = str(row.get("テキスト", "")).strip()
                if text_name == "nan": text_name = ""
                unit = str(row.get("単元", "")).strip()
                if unit == "nan": unit = ""
                end_page = str(row.get("終了ページ", "")).strip()
                if end_page == "nan": end_page = ""
                
                if end_page:
                    progress = "\n　" + end_page.replace("\n", "\n　") if "\n" in end_page else end_page
                elif text_name:
                    progress = f"{text_name} {unit}".strip()
                else:
                    progress = "（未入力）"
                
                concentration = row.get("集中力", "")
                reaction = row.get("ミスへの反応", "")
                attitude = f"集中力: {concentration} / ミスへの反応: {reaction}" if concentration or reaction else "（未入力）"
                
                advice = str(row.get("アドバイス", "")).strip()
                parent_msg = str(row.get("保護者への連絡", "")).strip()

                class_text = f"📅 【授業内容】（{period} / {subject} / 担当：{teacher}）\n・進捗：{progress}\n・様子：{attitude}"
                class_sections.append(class_text)

                if advice and advice != "nan":
                    advice_sections.append(f"《{subject} / {teacher}先生より》\n{advice}")
                if parent_msg and parent_msg != "nan":
                    parent_msg_sections.append(f"《{subject} / {teacher}先生より》\n{parent_msg}")

            classes_text = "\n\n".join(class_sections)
            advices_text = "\n\n".join(advice_sections) if advice_sections else "（特になし）"
            msgs_text = "\n\n".join(parent_msg_sections) if parent_msg_sections else "（特になし）"

            # ==========================================
            # ② その生徒の「小テスト結果」の抽出
            # ==========================================
            quiz_text = "小テストは実施していません"
            if not df_all_quizzes.empty and "APIエラー発生" not in df_all_quizzes.columns:
                df_all_quizzes['日時'] = pd.to_datetime(df_all_quizzes['日時'], format='mixed', errors='coerce')
                student_quizzes = df_all_quizzes[(df_all_quizzes['名前'] == student_name) & (df_all_quizzes['日時'].dt.date == target_date)]
                
                if not student_quizzes.empty:
                    quiz_results = [f"【{row.get('テキスト', '不明')} {row.get('単元', '不明')}】: {row.get('点数', '不明')}点" for _, row in student_quizzes.iterrows()]
                    quiz_text = "\n・".join(quiz_results)

            # ==========================================
            # ③ その生徒の「学校課題アラート」の抽出
            # ==========================================
            hw_alert_text = ""
            if not df_hw.empty and "APIエラー発生" not in df_hw.columns:
                student_hw = df_hw[(df_hw['生徒名'] == student_name) & (df_hw['ステータス'] != '提出済')].copy()
                
                if not student_hw.empty:
                    student_hw['提出期限'] = pd.to_datetime(student_hw['提出期限']).dt.date
                    student_hw = student_hw.sort_values('提出期限')
                    
                    alerts = []
                    today = datetime.date.today()
                    
                    for _, row in student_hw.iterrows():
                        days_left = (row['提出期限'] - today).days
                        if days_left < 0:
                            alerts.append(f"❌【期限超過！】{row['教科']}: {row['課題内容']}（{row['提出期限']}）")
                        elif days_left <= 3:
                            alerts.append(f"🚨【期限直前！】{row['教科']}: {row['課題内容']}（あと{days_left}日）")
                        elif days_left <= 7:
                            alerts.append(f"📅【期限間近】{row['教科']}: {row['課題内容']}（{row['提出期限']}）")
                    
                    if alerts:
                        hw_alert_text = "\n⚠️ 【学校課題の提出アラート】\n" + "\n".join(alerts) + "\n"

            # ==========================================
            # 📱 LINEメッセージの組み立てと表示
            # ==========================================
            line_message = f"""保護者様

お世話になっております。本日の {student_name} さんの授業報告をいたします。

{classes_text}

💯 【小テスト結果】
・{quiz_text}
{hw_alert_text}
🗣️ 【担当講師より（アドバイス等）】
{advices_text}

📢 【ご連絡事項】
{msgs_text}

ご不明な点がございましたら、お気軽にご連絡ください。
引き続きよろしくお願いいたします。
槌屋"""

            # 🌟 生徒ごとにアコーディオン（折りたたみ）形式で表示！
            with st.expander(f"📱 {student_name} さんのレポート", expanded=False):
                st.code(line_message, language="text")
                st.caption("👆 右上のコピーボタンを押してそのままLINEへペースト！")