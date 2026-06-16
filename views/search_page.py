import streamlit as st
import pandas as pd
import datetime 
import time

from utils.g_sheets import (
    get_student_master,
    get_all_logs,          # 🌟 変更: キャッシュ付きの統合ログ取得関数
    delete_specific_log    
)
from utils.api_guard import robust_api_call

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())


def render_search_page():
    st.header("🔍 全生徒の過去ログ検索 ＆ 修正")
    
    # ==========================================
    # 🌟 生徒リストの取得（マスターからID付きで）
    # ==========================================
    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    student_options = []
    if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
        student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()

    if st.session_state.get('role') == 'admin':
        with st.expander("🗑️ 間違えて入力した授業記録を削除する (教室長のみ)"):
            st.warning("※スプレッドシートから直接データを消去します。元には戻せません。")
            with st.form("delete_log_form"):
                d_col1, d_col2, d_col3 = st.columns(3)
                
                del_student_option = d_col1.selectbox("削除する生徒", student_options if student_options else ["-- データなし --"])
                del_date = d_col2.date_input("間違えた授業日", datetime.date.today())
                time_slots = [
                    "Aコマ目 (9:30~11:00)", "Bコマ目 (11:10~12:40)",
                    "0コマ目 (13:10~14:40)", "1コマ目 (14:50~16:20)",
                    "2コマ目 (16:40~18:10)", "3コマ目 (18:20~19:50)", "4コマ目 (20:00~21:30)"
                ]
                del_period = d_col3.selectbox("間違えた授業コマ", time_slots)
                
                if st.form_submit_button("🚨 この記録を削除する", type="primary"):
                    if del_student_option == "-- データなし --":
                        st.error("生徒が選択されていません。")
                    else:
                        # 🌟 IDと名前を分割
                        del_id = del_student_option.split(" - ")[0]
                        del_name = del_student_option.split(" - ")[1]
                        date_str = del_date.strftime("%Y/%m/%d")
                        
                        with st.spinner("データを削除中..."):
                            # 🌟 変更：del_subject を del_period に変更して関数に渡す
                            success = robust_api_call(delete_specific_log, del_id, del_name, date_str, del_period, fallback_value=False)
                            
                        if success:
                            # 🌟 成功時のメッセージも del_period を表示するように変更
                            st.success(f"✅ {date_str} の {del_name} さん ({del_period}) の記録を削除しました！")
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("⚠️ 該当する記録が見つかりませんでした。日付や授業コマを確認してください。（または通信エラーの可能性があります）")
    
    st.divider()

    if not student_options: 
        st.warning("生徒が登録されていません。（または通信エラーによりデータを取得できませんでした）")
        return

    with st.spinner("データベースから一括読み込み中...（超高速🚀）"):
        # 🌟 変更: 統合シートのデータを一括で持ってくる
        df_all = cached_get_all_logs()
    
    if df_all.empty or "APIエラー発生" in df_all.columns: 
        st.info("まだ授業記録がないか、通信エラーによりデータを取得できませんでした。")
        return
        
    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    
    # 🌟 名前列の統一処理（表示をキレイにするため）
    if '名前' in df_all.columns:
        if '生徒名' in df_all.columns:
            df_all = df_all.drop(columns=['名前'])
        else:
            df_all = df_all.rename(columns={'名前': '生徒名'})
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        min_date = df_all['日時'].min().date() if not pd.isnull(df_all['日時'].min()) else datetime.date.today()
        max_date = df_all['日時'].max().date() if not pd.isnull(df_all['日時'].max()) else datetime.date.today()
        date_range = c1.date_input("📅 日付の範囲", [min_date, max_date])
        
        # 担当講師リストの作成（None対策）
        if '担当講師' in df_all.columns:
            valid_teachers = [t for t in df_all['担当講師'].dropna().unique() if t and str(t).strip() not in ["None", "nan", ""]]
            teachers = ["すべて"] + valid_teachers
        else:
            teachers = ["すべて"]
            
        selected_teacher = c2.selectbox("👨‍🏫 担当講師", teachers)
        
        # 生徒リストは「ID - 名前」のプルダウンにする
        students = ["すべて"] + student_options
        selected_student_option = c3.selectbox("👤 生徒名", students)

    # ==========================================
    # 🌟 絞り込み処理
    # ==========================================
    df_filtered = df_all.copy()
    
    if len(date_range) == 2: 
        df_filtered = df_filtered[(df_filtered['日時'].dt.date >= date_range[0]) & (df_filtered['日時'].dt.date <= date_range[1])]
        
    if selected_teacher != "すべて": 
        df_filtered = df_filtered[df_filtered['担当講師'] == selected_teacher]
        
    if selected_student_option != "すべて":
        search_id = selected_student_option.split(" - ")[0]
        search_name = selected_student_option.split(" - ")[1]
        
        # 🌟 生徒ID列があればIDで絞り込み、なければ名前で絞り込む
        if '生徒ID' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['生徒ID'].astype(str) == search_id]
        else:
            df_filtered = df_filtered[df_filtered['生徒名'] == search_name]

    st.success(f"該当記録: **{len(df_filtered)} 件**")
    
    # 日付をキレイな文字列に変換
    df_filtered['日時'] = df_filtered['日時'].dt.strftime('%Y/%m/%d')
    
    # 見た目を整える魔法
    df_display = df_filtered.drop(columns=['ページ数'], errors='ignore')
    # NaN を空文字に変換
    df_display = df_display.fillna("") 
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)