import streamlit as st
import datetime
import pandas as pd

# 🌟 変更: 不要な関数を消し、一括データ取得用の関数をインポート
from utils.g_sheets import (
    get_student_master,
    get_all_logs,
    load_quiz_records, 
    load_school_homework_data 
)
from utils.api_guard import robust_api_call

# 🌟 キャッシュを使った爆速読み込み関数
@st.cache_data(ttl=600)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def render_line_report_page():
    st.header("📱 LINE用 授業報告レポート生成")
    st.write("授業記録・小テストに加え、**学校課題の提出アラート**も自動生成します✨")

    # 1. 🌟 生徒と日付の選択エリア（マスターデータ活用版）
    col1, col2 = st.columns(2)
    
    df_students = cached_get_student_master()
    if df_students.empty:
        st.error("生徒データの取得に失敗しました。")
        st.stop()
        
    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    
    selected_student_option = col1.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_options)
    selected_date = col2.date_input("📅 授業日を選択", datetime.date.today())

    if selected_student_option == "-- 選択 --":
        st.info("👆 レポートを作成する生徒と日付を選択してください。")
        st.stop()

    # 🌟 IDと名前を分割
    student_id = selected_student_option.split(" - ")[0]
    student_name = selected_student_option.split(" - ")[1]

    st.divider()

    with st.spinner("スプレッドシートからデータを取得中...（超高速🚀）"):
        date_str = selected_date.strftime("%Y/%m/%d")

        # --- 🌟 ① 授業記録の取得（統合データから抽出） ---
        df_all_logs = cached_get_all_logs()
        
        class_sections = []
        advice_sections = []
        parent_msg_sections = []

        if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns:
            # 🌟 指定した生徒のデータだけを抽出（ID優先、なければ名前）
            if student_id != "未設定" and '生徒ID' in df_all_logs.columns:
                df_classes = df_all_logs[df_all_logs['生徒ID'].astype(str) == str(student_id)].copy()
            else:
                name_col = '名前' if '名前' in df_all_logs.columns else '生徒名'
                df_classes = df_all_logs[df_all_logs[name_col] == student_name].copy()

            if not df_classes.empty:
                # 日付型に変換して選択日と一致するものを抽出
                df_classes['日時'] = pd.to_datetime(df_classes['日時'], format='mixed', errors='coerce')
                target_date = pd.to_datetime(selected_date).date()
                daily_classes = df_classes[df_classes['日時'].dt.date == target_date]

                if not daily_classes.empty:
                    # 複数コマある場合はループで回してテキストを作成
                    for _, row in daily_classes.iterrows():
                        teacher = row.get("担当講師", "（未入力）")
                        subject = row.get("科目", "（未入力）")
                        period = row.get("授業コマ", "（未入力）")
                        
                        text_name = str(row.get("テキスト", "")).strip()
                        if text_name == "nan": text_name = ""
                        
                        unit = str(row.get("単元", "")).strip()
                        if unit == "nan": unit = ""
                        
                        end_page = str(row.get("終了ページ", "")).strip()
                        if end_page == "nan": end_page = ""
                        
                        # 終了ページの列に入力がある場合は、それを最優先して表示！
                        if end_page:
                            if "\n" in end_page:
                                progress = "\n　" + end_page.replace("\n", "\n　")
                            else:
                                progress = end_page
                        elif text_name:
                            progress = f"{text_name} {unit}".strip()
                        else:
                            progress = "（未入力）"
                        
                        concentration = row.get("集中力", "")
                        reaction = row.get("反応", "")
                        attitude = f"集中力: {concentration} / 反応: {reaction}" if concentration or reaction else "（未入力）"
                        
                        advice = str(row.get("アドバイス", "")).strip()
                        parent_msg = str(row.get("保護者への連絡", "")).strip()

                        # 授業ごとのブロックを作成
                        class_text = f"📅 【授業内容】（{period} / {subject} / 担当：{teacher}）\n・進捗：{progress}\n・様子：{attitude}"
                        class_sections.append(class_text)

                        # アドバイスや連絡事項がある場合のみ追加
                        if advice and advice != "nan":
                            advice_sections.append(f"《{subject} / {teacher}先生より》\n{advice}")
                        if parent_msg and parent_msg != "nan":
                            parent_msg_sections.append(f"《{subject} / {teacher}先生より》\n{parent_msg}")

        # 万が一授業データが見つからなかった場合の処理
        if not class_sections:
            st.warning(f"⚠️ {date_str} の {student_name} さんの授業記録が見つかりません。")
            classes_text = "📅 【授業内容】\n（データが見つかりませんでした）"
            advices_text = "（特になし）"
            msgs_text = "（特になし）"
        else:
            classes_text = "\n\n".join(class_sections)
            advices_text = "\n\n".join(advice_sections) if advice_sections else "（特になし）"
            msgs_text = "\n\n".join(parent_msg_sections) if parent_msg_sections else "（特になし）"


        # --- 🌟 ② 小テスト結果の取得（統合データから抽出） ---
        df_all_quizzes = cached_load_quiz_records()
        quiz_text = "小テストは実施していません"
        
        if not df_all_quizzes.empty and "APIエラー発生" not in df_all_quizzes.columns:
            # 🌟 名前で抽出
            df_quiz = df_all_quizzes[df_all_quizzes['名前'] == student_name].copy()
            
            if not df_quiz.empty:
                df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
                target_date = pd.to_datetime(selected_date).date()
                daily_quiz = df_quiz[df_quiz['日時'].dt.date == target_date]
                
                if not daily_quiz.empty:
                    quiz_results = []
                    for _, row in daily_quiz.iterrows():
                        quiz_results.append(f"【{row.get('テキスト', '不明')} {row.get('単元', '不明')}】: {row.get('点数', '不明')}点")
                    quiz_text = "\n・".join(quiz_results)
        elif "APIエラー発生" in df_all_quizzes.columns:
            quiz_text = "（⚠️通信エラーにより小テスト結果を取得できませんでした）"


        # --- ③ 学校課題アラートの自動生成（そのまま、student_nameを使用） ---
        df_hw = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
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
                    hw_alert_text = "\n" + "\n".join(alerts)

        # ==========================================
        # 📱 LINEメッセージの組み立て
        # ==========================================
        st.subheader("📋 完成したLINEメッセージ")
        
        hw_section = ""
        if hw_alert_text:
            hw_section = f"\n⚠️ 【学校課題の提出アラート】{hw_alert_text}\n"

        line_message = f"""保護者様

お世話になっております。本日の {student_name} さんの授業報告をいたします。

{classes_text}

💯 【小テスト結果】
・{quiz_text}
{hw_section}
🗣️ 【担当講師より（アドバイス等）】
{advices_text}

📢 【ご連絡事項】
{msgs_text}

ご不明な点がございましたら、お気軽にご連絡ください。
引き続きよろしくお願いいたします。"""

        st.code(line_message, language="text")
        st.caption("👆 右上のコピーボタンを押してLINEへ！")