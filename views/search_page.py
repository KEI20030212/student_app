import streamlit as st
import pandas as pd
import datetime 
import time

from utils.g_sheets import get_student_master, delete_specific_log
from utils.api_guard import robust_api_call
from views.search_tab_lesson import render_lesson_tab
from views.search_tab_quiz import render_quiz_tab

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

# 全データを取得する処理（削除プレビュー用に追加）
def cached_get_all_logs():
    from utils.g_sheets import get_all_logs
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

def render_search_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🔍 全生徒の過去ログ検索 ＆ 修正")
    with col_r:
        st.write("")
        if st.button("🔄 データを更新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # 生徒リストの取得
    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    student_options = []
    if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
        student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    # ==========================================
    # 🌟 削除機能（プレビュー＆選択式に超絶アップグレード！）
    # ==========================================
    user_role = st.session_state.get('role', '')
    allowed_roles = ['admin', 'owner', 'am', 'head_teacher']

    if user_role in allowed_roles:
        with st.expander("🗑️ 間違えて入力した授業記録を削除する"):
            today = datetime.date.today()
            
            if user_role == 'admin':
                st.warning("※スプレッドシートから直接データを消去します。元には戻せません。")
                min_del_date = today - datetime.timedelta(days=3650)
                max_del_date = today
            else:
                st.warning("⚠️ 安全対策のため、削除できるのは【今日と昨日】の記録のみです。")
                min_del_date = today - datetime.timedelta(days=1)
                max_del_date = today

            st.info("💡 **特定の記録を選んで削除:** \n削除したい生徒・日付・コマを選択すると、下に候補が表示されます。内容を確認して削除ボタンを押してください。")
            
            # 🌟 フォームを廃止し、選んだ瞬間にプレビューが出るように変更！
            d_col1, d_col2, d_col3 = st.columns(3)
            del_student_option = d_col1.selectbox("削除する生徒", student_options if student_options else ["-- データなし --"])
            del_date = d_col2.date_input("間違えた授業日", value=today, min_value=min_del_date, max_value=max_del_date)
            time_slots = [
                "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
                "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
            ]
            del_period = d_col3.selectbox("間違えた授業コマ", time_slots)
            
            if del_student_option != "-- データなし --":
                del_id = del_student_option.split(" - ")[0]
                del_name = del_student_option.split(" - ")[1]
                date_str = del_date.strftime("%Y/%m/%d")
                
                # 全データから該当する記録を探す
                df_all = cached_get_all_logs()
                
                if not df_all.empty:
                    # 選ばれた条件で絞り込み
                    df_target = df_all[
                        (df_all['生徒ID'].astype(str) == str(del_id)) & 
                        (df_all['日時'].astype(str).str.contains(date_str, na=False, regex=False)) & 
                        (df_all['授業コマ'] == del_period)
                    ]
                    
                    st.write("---") # 区切り線
                    
                    # 🌟 プレビュー表示エリア
                    if df_target.empty:
                        st.info("🔍 指定された条件の記録は見つかりませんでした。")
                    else:
                        st.warning(f"⚠️ {len(df_target)}件の記録が見つかりました。削除したい記録のボタンを押してください。")
                        
                        # 見つかった記録を1つずつカード状に表示する
                        for idx, row in df_target.iterrows():
                            teacher = str(row.get('担当講師', '未入力'))
                            subject = str(row.get('科目', '未入力'))
                            advice = str(row.get('アドバイス', ''))
                            
                            with st.container(border=True):
                                st.markdown(f"**👨‍🏫 講師:** {teacher} | **📚 科目:** {subject}")
                                st.caption(f"**💬 アドバイス:** {advice[:50]}...")
                                
                                # それぞれの記録に専用の削除ボタンをつける！
                                if st.button("🚨 この記録を削除する", key=f"del_btn_{idx}", type="primary"):
                                    with st.spinner("データを削除中..."):
                                        # 新しく追加した advice の文章も手がかりとして裏側に渡す！
                                        success = robust_api_call(
                                            delete_specific_log, 
                                            del_id, del_name, date_str, del_period, advice, 
                                            fallback_value=False, notify=False
                                        )
                                        
                                    if success:
                                        st.success("✅ 指定された記録を安全に削除しました！")
                                        st.cache_data.clear()
                                        time.sleep(1.5)
                                        st.rerun()
                                    else:
                                        st.error("⚠️ 削除に失敗しました。")
    
    st.divider()

    if not student_options: 
        st.warning("生徒が登録されていません。（または通信エラーによりデータを取得できませんでした）")
        return

    # タブ構造
    tab_lesson, tab_quiz = st.tabs(["📝 授業記録の検索", "💯 小テスト記録の検索"])

    with tab_lesson:
        render_lesson_tab(student_options)
        
    with tab_quiz:
        render_quiz_tab(student_options)