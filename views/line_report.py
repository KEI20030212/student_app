import streamlit as st
import datetime
import pandas as pd
from utils.g_sheets import (
    get_all_student_names,
    load_quiz_data_from_dedicated_sheet,
    load_daily_class_record,
    load_school_homework_data  # 🌟 追加：学校課題データを読み込む関数
)

def render_line_report_page():
    st.header("📱 LINE用 授業報告レポート生成")
    st.write("授業記録・小テストに加え、**学校課題の提出アラート**も自動生成します✨")

    # 1. 生徒と日付の選択エリア
    col1, col2 = st.columns(2)
    student_names = get_all_student_names()
    selected_student = col1.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    selected_date = col2.date_input("📅 授業日を選択", datetime.date.today())

    if selected_student == "-- 選択 --":
        st.info("👆 レポートを作成する生徒と日付を選択してください。")
        st.stop()

    st.divider()

    with st.spinner("スプレッドシートからデータを取得中..."):
        date_str = selected_date.strftime("%Y/%m/%d")

        # --- ① 授業記録の取得 ---
        class_record = load_daily_class_record(selected_student, date_str)
        if not class_record:
            st.warning(f"⚠️ {date_str} の {selected_student} さんの授業記録が見つかりません。")
            teacher_name = "（不明）"; subject = "（未入力）"; period = "（未入力）"
            progress = "（未入力）"; attitude = "（未入力）"; advice = "（特になし）"; parent_msg = "（特になし）"
        else:
            teacher_name = class_record.get("担当講師", "（未入力）")
            subject = class_record.get("科目", "（未入力）")
            period = class_record.get("授業コマ", "（未入力）")
            text_name = class_record.get("テキスト", ""); unit = class_record.get("単元", ""); end_page = class_record.get("終了ページ", "")
            progress = f"{text_name} {unit}（〜{end_page}P）" if text_name else "（未入力）"
            concentration = class_record.get("集中力", ""); reaction = class_record.get("反応", "")
            attitude = f"集中力: {concentration} / 反応: {reaction}" if concentration or reaction else "（未入力）"
            advice = class_record.get("アドバイス", "（特になし）")
            parent_msg = class_record.get("保護者への連絡", "（特になし）")

        # --- ② 小テスト結果の取得 ---
        df_quiz = load_quiz_data_from_dedicated_sheet(selected_student)
        quiz_text = "小テストは実施していません"
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            target_date = pd.to_datetime(selected_date).date()
            daily_quiz = df_quiz[df_quiz['日時'].dt.date == target_date]
            if not daily_quiz.empty:
                quiz_results = []
                for _, row in daily_quiz.iterrows():
                    quiz_results.append(f"【{row.get('テキスト', '不明')} {row.get('単元', '不明')}】: {row.get('点数', '不明')}点")
                quiz_text = "\n・".join(quiz_results)

        # --- 🌟 ③ 【New!】学校課題アラートの自動生成 ---
        df_hw = load_school_homework_data()
        hw_alert_text = ""
        
        if not df_hw.empty:
            # 選択された生徒の「提出済」以外の課題を抽出
            student_hw = df_hw[(df_hw['生徒名'] == selected_student) & (df_hw['ステータス'] != '提出済')].copy()
            
            if not student_hw.empty:
                # 期限を日付型に変換してソート
                student_hw['提出期限'] = pd.to_datetime(student_hw['提出期限']).dt.date
                student_hw = student_hw.sort_values('提出期限')
                
                alerts = []
                today = datetime.date.today()
                
                for _, row in student_hw.iterrows():
                    days_left = (row['提出期限'] - today).days
                    
                    # 期限切れ、または期限まで7日以内のものだけアラートに載せる
                    if days_left < 0:
                        alerts.append(f"❌【期限超過！】{row['教科']}: {row['課題内容']}（{row['提出期限']}）")
                    elif days_left <= 3:
                        alerts.append(f"🚨【期限直前！】{row['教科']}: {row['課題内容']}（あと{days_left}日）")
                    elif days_left <= 7:
                        alerts.append(f"📅【期限間近】{row['教科']}: {row['課題内容']}（{row['提出期限']}）")
                
                if alerts:
                    hw_alert_text = "\n" + "\n".join(alerts)

        # ==========================================
        # 📱 LINEメッセージの組み立て
        # ==========================================
        st.subheader("📋 完成したLINEメッセージ")
        
        # 学校課題がある場合だけ、項目を表示する
        hw_section = ""
        if hw_alert_text:
            hw_section = f"\n⚠️ 【学校課題の提出アラート】{hw_alert_text}\n"

        line_message = f"""保護者様

お世話になっております。本日の {selected_student} さんの授業報告をいたします。
（担当講師：{teacher_name}）

📅 【授業内容】（{date_str} {period}）
・科目：{subject}
・進捗：{progress}
・様子：{attitude}

💯 【小テスト結果】
・{quiz_text}
{hw_section}
🗣️ 【担当講師より（アドバイス等）】
{advice}

📢 【ご連絡事項】
{parent_msg}

ご不明な点がございましたら、お気軽にご連絡ください。
引き続きよろしくお願いいたします。"""

        st.code(line_message, language="text")
        st.caption("👆 右上のコピーボタンを押してLINEへ！")