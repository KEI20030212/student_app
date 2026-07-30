import streamlit as st
import pandas as pd
import time
import datetime
import re 

from utils.g_sheets import (
    load_board_message,
    save_board_message,
    get_all_logs,      
    load_quiz_records,
    load_transfer_requests 
)
from utils.api_guard import robust_api_call

def safe_get_all_logs():
    df = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def safe_load_quiz_records():
    df = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

# 🌟 修正：シートIDを受け取ってデータを読み込むように変更
def safe_load_transfer_requests(sheet_id):
    df = robust_api_call(load_transfer_requests, sheet_id, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def render_home_page():
    st.header("📢 連絡掲示板")
    
    user_role = st.session_state.get('role', '')

    # ==========================================
    # 🌟 1. オーナー・管理者専用：振替申請アラート
    # ==========================================
    if user_role in ['admin', 'owner']:
        
        # 🌟 ここで2校舎分のスプレッドシートIDを設定！
        TABATA_SHEET_ID = "1j93KTSKjywAQoslEPt-osRMzOMSiheb8GrT77gLgPko" 
        HIGASHI_JUJO_SHEET_ID = "1lY7t4gmeFClaWuVOC1DUb-18d3rK81OU5P_F5DabJeQ"
        
        col_t1, col_t2 = st.columns([0.8, 0.2], vertical_alignment="bottom")
        with col_t1:
            st.subheader("🛎️ 振替申請アラート")
        with col_t2:
            if st.button("🔄 最新を確認", key="btn_update_transfers", use_container_width=True):
                # load_transfer_requests の全キャッシュ（両校舎分）を一撃でクリア
                load_transfer_requests.clear()
                st.rerun()

        def render_transfer_alerts(df_transfers, branch_name, sheet_id):
            if not df_transfers.empty:
                df_transfers.columns = df_transfers.columns.str.strip().str.replace('\n', '')
                df_transfers = df_transfers.fillna("")
                
                if 'タイムスタンプ' in df_transfers.columns:
                    df_transfers['タイムスタンプ_dt'] = pd.to_datetime(df_transfers['タイムスタンプ'], format='mixed', errors='coerce')
                    
                    # データを新しい順に並べ替え
                    df_transfers = df_transfers.sort_values('タイムスタンプ_dt', ascending=False)
                    
                    # 7日前を境界線にして、データを「直近」と「過去」に真っ二つに分ける
                    seven_days_ago = pd.Timestamp.now() - pd.Timedelta(days=7)
                    recent_transfers = df_transfers[df_transfers['タイムスタンプ_dt'] >= seven_days_ago]
                    past_transfers = df_transfers[df_transfers['タイムスタンプ_dt'] < seven_days_ago]
                    
                    # 👉 共通処理：1件ずつカード形式で表示する関数を中に作る
                    def draw_transfer_cards(df_target):
                        for _, row in df_target.iterrows():
                            dt_val = row['タイムスタンプ_dt']
                            ts = dt_val.strftime('%m/%d %H:%M') if pd.notna(dt_val) else "不明"
                            
                            student = str(row.get('生徒氏名', '不明')).strip()
                            
                            absent_date_raw = str(row.get('欠席予定の授業日', '不明')).strip()
                            absent_date = absent_date_raw.split(' ')[0] if absent_date_raw else "不明"
                            absent_time = str(row.get('欠席予定の授業時間', '')).strip()
                            
                            with st.expander(f"👤 {student} 様 （送信: {ts} / 欠席予定: {absent_date}）"):
                                st.markdown(f"**■ 欠席予定:** {absent_date} {absent_time}")
                                st.markdown(f"**■ 理由:** {row.get('お振替の理由', '')}")
                                
                                hope_days = []
                                for col in df_transfers.columns:
                                    if "曜日" in col and "[" in col and "]" in col:
                                        val = str(row.get(col, '')).strip()
                                        if val: 
                                            day_match = re.search(r'\[(.*?)\]', col)
                                            day_name = day_match.group(1) if day_match else col
                                            hope_days.append(f"{day_name}: {val}")
                                
                                if hope_days:
                                    st.markdown(f"**■ 振替希望:**\n" + " \n".join([f"- {h}" for h in hope_days]))
                                    
                                st.markdown(f"**■ 希望時間:** {row.get('お振替希望授業時間', '')}")
                                st.markdown(f"**■ 備考:** {row.get('備考欄', '')}")
                                st.markdown(f"[🔗 スプレッドシートで全回答を確認する](https://docs.google.com/spreadsheets/d/{sheet_id}/edit)")

                    # 🌟 1. 直近7日間のデータを常時表示
                    if not recent_transfers.empty:
                        st.warning(f"🔔 【{branch_name}】直近7日以内に **{len(recent_transfers)}件** の申請が届いています！")
                        draw_transfer_cards(recent_transfers)
                    else:
                        st.info(f"💡 【{branch_name}】直近7日以内の新しい振替申請はありません。")

                    # 🌟 2. 過去のデータをアコーディオンに格納して表示
                    if not past_transfers.empty:
                        with st.expander(f"📂 【{branch_name}】過去の振替申請履歴（全 {len(past_transfers)}件）"):
                            draw_transfer_cards(past_transfers)
            else:
                st.info(f"💡 【{branch_name}】まだデータがありません。（またはシートが見つかりません）")

        # 🌟 タブを廃止し、縦に並べて表示するように変更
        with st.container(border=True):
            st.markdown("#### 🏫 田端新町校")
            df_tabata = safe_load_transfer_requests(TABATA_SHEET_ID)
            render_transfer_alerts(df_tabata, "田端新町校", TABATA_SHEET_ID)
            
            st.write("") # 少し余白をあける
            
            st.markdown("#### 🏫 東十条駅前校")
            df_higashi = safe_load_transfer_requests(HIGASHI_JUJO_SHEET_ID)
            render_transfer_alerts(df_higashi, "東十条駅前校", HIGASHI_JUJO_SHEET_ID)

    # ==========================================
    # 🌟 2. 社員・管理者向け：小テストURL抜け検知アラート
    # ==========================================
    if user_role in ['admin', 'owner', 'head_teacher', 'am']:
        df_logs = safe_get_all_logs() 
        df_quizzes = safe_load_quiz_records() 
        today = datetime.date.today()
        
        if not df_logs.empty and "APIエラー発生" not in df_logs.columns:
            df_logs['日時'] = pd.to_datetime(df_logs['日時'], format='mixed', errors='coerce')
            today_logs = df_logs[df_logs['日時'].dt.date == today]
            
            if not today_logs.empty:
                name_col = '名前' if '名前' in today_logs.columns else '生徒名'
                today_students = today_logs[name_col].drop_duplicates().tolist()
                
                missing_url_students = []
                for student in today_students:
                    # 👇 変更：その生徒の今日の授業ログを絞り込み、Myeトレを使ったか確認
                    student_classes_today = today_logs[today_logs[name_col] == student]
                    used_myetore = any("Myeトレ" in str(row.get("テキスト", "")) for _, row in student_classes_today.iterrows())

                    has_quiz = False
                    if not df_quizzes.empty and "APIエラー発生" not in df_quizzes.columns:
                        df_quizzes['日時'] = pd.to_datetime(df_quizzes['日時'], format='mixed', errors='coerce')
                        student_quizzes = df_quizzes[(df_quizzes['名前'] == student) & (df_quizzes['日時'].dt.date == today)]
                        if not student_quizzes.empty:
                            has_quiz = True
                            
                    # 👇 変更：小テストがなく、かつMyeトレもやっていない生徒だけをエラーにする
                    if not has_quiz and not used_myetore:
                        missing_url_students.append(student)
                        
                if missing_url_students:
                    st.error(f"🚨 **【答案確認URL 未添付アラート】**\n\n本日授業記録がある以下の生徒は、小テスト結果が未登録のためLINE報告書にDriveのURLが添付されていません。画像アップロードと小テスト結果の登録漏れがないか確認してください。\n\n**{', '.join(missing_url_students)}**")

    st.divider()
    
    # ==========================================
    # 🌟 3. 全講師向け：掲示板エリア
    # ==========================================
    st.subheader("📌 講師向け 連絡事項")
    
    board_data = robust_api_call(load_board_message, fallback_value={"message": "", "updated_at": "---"})
    current_message = board_data.get("message", "本日の連絡事項はありません。")
    updated_at = board_data.get("updated_at", "---")
    
    if updated_at and updated_at != "---":
        st.caption(f"🕒 最終更新日時: {updated_at}")
    
    st.info(current_message.replace('\n', '  \n'))
    
    if user_role in ['admin', 'owner', 'am']:
        with st.expander("✏️ 掲示板を編集"):
            new_msg = st.text_area("内容を入力", value=current_message, height=100)
            if st.button("💾 掲示板を更新"):
                with st.spinner("更新中..."):
                    success = robust_api_call(lambda: save_board_message(new_msg), fallback_value=False)
                    if success is not False:
                        load_board_message.clear()
                        st.success("更新しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("通信エラーにより更新できませんでした。")