import streamlit as st
import pandas as pd
import datetime 
import time

from utils.g_sheets import (
    get_student_master,
    get_all_logs,          
    delete_specific_log,
    load_quiz_records  # 🌟 追加：小テスト記録の読み込み関数
)
from utils.api_guard import robust_api_call

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

# 🌟 新設：二重キャッシュ防止のため、ここには@st.cache_dataを付けずに原本を直接呼び出す！
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())


def render_search_page():
    # タイトル横に「データを更新」ボタンを配置
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🔍 全生徒の過去ログ検索 ＆ 修正")
    with col_r:
        st.write("")
        if st.button("🔄 データを更新", use_container_width=True):
            st.cache_data.clear() # キャッシュを強制クリアして最新化
            st.rerun()

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
                        del_id = del_student_option.split(" - ")[0]
                        del_name = del_student_option.split(" - ")[1]
                        date_str = del_date.strftime("%Y/%m/%d")
                        
                        with st.spinner("データを削除中..."):
                            success = robust_api_call(delete_specific_log, del_id, del_name, date_str, del_period, fallback_value=False)
                            
                        if success:
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

    # 🌟 変更点: 大元のタブ構造を作成して、授業記録と小テスト記録を分離
    tab_lesson, tab_quiz = st.tabs(["📝 授業記録の検索", "💯 小テスト記録の検索"])

    # ==========================================
    # 📝 タブ1: 授業記録の検索（既存の全ロジック）
    # ==========================================
    with tab_lesson:
        with st.spinner("授業データベースから読み込み中...🚀"):
            df_all = cached_get_all_logs()
        
        if df_all.empty or "APIエラー発生" in df_all.columns: 
            st.info("まだ授業記録がないか、通信エラーによりデータを取得できませんでした。")
        else:
            df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
            
            if '名前' in df_all.columns:
                if '生徒名' in df_all.columns:
                    df_all = df_all.drop(columns=['名前'])
                else:
                    df_all = df_all.rename(columns={'名前': '生徒名'})
            
            with st.container(border=True):
                st.markdown("**🔍 授業記録の検索条件と表示設定**")
                c1, c2, c3 = st.columns(3)
                min_date = df_all['日時'].min().date() if not pd.isnull(df_all['日時'].min()) else datetime.date.today()
                max_date = df_all['日時'].max().date() if not pd.isnull(df_all['日時'].max()) else datetime.date.today()
                date_range = c1.date_input("📅 日付の範囲", [min_date, max_date], key="lesson_date_range")
                
                if '科目' in df_all.columns:
                    valid_subjects = [s for s in df_all['科目'].dropna().unique() if s and str(s).strip() not in ["None", "nan", ""]]
                    subjects = ["すべて"] + valid_subjects
                else:
                    subjects = ["すべて"]
                    
                selected_subject = c2.selectbox("📚 科目", subjects, key="lesson_subject")
                
                students = ["すべて"] + student_options
                selected_student_option = c3.selectbox("👤 生徒名", students, key="lesson_student")

                st.write("")
                all_columns_list = [
                    "日時", "生徒ID", "生徒名", "科目", "テキスト", "終了ページ", 
                    "担当講師", "授業形態", "出欠", "授業コマ", "アドバイス", 
                    "保護者への連絡", "次回への引継ぎ", "出した宿題P", "やった宿題P", 
                    "やる気ランク", "未達成の理由", "本日の修正策", "次回の宿題テキスト", 
                    "次回の宿題ページ数", "遅刻時間", "集中力", "ミスへの反応", "次回の持ち物"
                ]
                
                available_cols = [col for col in all_columns_list if col in df_all.columns or col == "日時"]
                default_cols = [col for col in ["日時", "生徒名", "科目", "終了ページ"] if col in available_cols]
                
                selected_display_cols = st.multiselect(
                    "📋 表に表示する項目（クリックでON/OFFを切り替え）",
                    options=available_cols,
                    default=default_cols,
                    key="lesson_display_cols"
                )

            # 絞り込み
            df_filtered = df_all.copy()
            if len(date_range) == 2: 
                df_filtered = df_filtered[(df_filtered['日時'].dt.date >= date_range[0]) & (df_filtered['日時'].dt.date <= date_range[1])]
            if selected_subject != "すべて": 
                df_filtered = df_filtered[df_filtered['科目'] == selected_subject]
            if selected_student_option != "すべて":
                search_id = selected_student_option.split(" - ")[0]
                search_name = selected_student_option.split(" - ")[1]
                if '生徒ID' in df_filtered.columns:
                    df_filtered = df_filtered[df_filtered['生徒ID'].astype(str) == search_id]
                else:
                    df_filtered = df_filtered[df_filtered['生徒名'] == search_name]

            df_filtered['日時'] = df_filtered['日時'].dt.strftime('%Y/%m/%d')
            df_display = df_filtered.drop(columns=['ページ数'], errors='ignore')
            df_display = df_display.fillna("") 

            # お留守番表示
            if df_display.empty:
                st.info("💡 指定された条件の授業記録は見つかりませんでした。\n日付の範囲を広げるか、他の生徒・科目を選択してみてください。")
            else:
                st.success(f"該当記録: **{len(df_filtered)} 件**")
                if selected_display_cols:
                    st.dataframe(df_display[selected_display_cols], use_container_width=True, hide_index=True)
                    
                    st.write("")
                    @st.dialog("💬 抽出された記録のコメント詳細")
                    def show_comment_details(df_subset):
                        st.write(f"検索結果の **{len(df_subset)}件** のコメントを表示します。")
                        st.divider()
                        comment_cols = [c for c in ["アドバイス", "保護者への連絡", "次回への引継ぎ"] if c in df_subset.columns]
                        if not comment_cols:
                            st.warning("詳細を表示できるコメント項目が存在しません。")
                            return
                        for idx, row in df_subset.iterrows():
                            with st.container(border=True):
                                st.markdown(f"**📅 {row.get('日時', '日付不明')} | 👤 {row.get('生徒名', '生徒名不明')} | 📚 {row.get('科目', '科目不明')} (👨‍🏫 {row.get('担当講師', '講師不明')})**")
                                has_any_comment = False
                                for col in comment_cols:
                                    comment_text = str(row[col]).strip()
                                    if comment_text and comment_text not in ["", "-", "nan", "None"]:
                                        st.caption(f"**【{col}】**")
                                        st.write(comment_text.replace('\n', '  \n'))
                                        has_any_comment = True
                                if not has_any_comment:
                                    st.caption("※特記すべきコメントはありませんでした。")

                    if st.button("💬 この検索結果の『コメント詳細』を別枠で読む", icon="👁️", use_container_width=True, key="btn_lesson_comment"):
                        show_comment_details(df_display)
                else:
                    st.warning("⚠️ 表示項目が何も選択されていません。項目を1つ以上選択してください。")

    # ==========================================
    # 💯 タブ2: 小テスト記録の検索（新規バルク対応）
    # ==========================================
    with tab_quiz:
        with st.spinner("小テストデータベースから読み込み中...🚀"):
            df_quiz_raw = cached_load_quiz_records()
            df_quiz = df_quiz_raw.copy()
        
        if df_quiz.empty or "APIエラー発生" in df_quiz.columns:
            st.info("💡 まだ小テスト記録がないか、通信エラーによりデータを取得できませんでした。")
        else:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            
            # 名前列の統一処理
            if '名前' in df_quiz.columns:
                if '生徒名' in df_quiz.columns:
                    df_quiz = df_quiz.drop(columns=['名前'])
                else:
                    df_quiz = df_quiz.rename(columns={'名前': '生徒名'})

            with st.container(border=True):
                st.markdown("**🔍 小テスト記録の検索条件と表示設定**")
                cq1, cq2 = st.columns(2)
                
                min_q_date = df_quiz['日時'].min().date() if not pd.isnull(df_quiz['日時'].min()) else datetime.date.today()
                max_q_date = df_quiz['日時'].max().date() if not pd.isnull(df_quiz['日時'].max()) else datetime.date.today()
                q_date_range = cq1.date_input("📅 日付の範囲", [min_q_date, max_q_date], key="quiz_date_range")
                
                q_students = ["すべて"] + student_options
                selected_q_student = cq2.selectbox("👤 生徒名", q_students, key="quiz_student")

                st.write("")
                # 小テスト用の表示項目カスタマイズ
                quiz_columns_list = ["日時", "生徒名", "テキスト", "単元", "点数", "ミス問題番号", "タイミング"]
                available_q_cols = [col for col in quiz_columns_list if col in df_quiz.columns or col == "日時"]
                default_q_cols = [col for col in ["日時", "生徒名", "テキスト", "単元", "点数"] if col in available_q_cols]

                selected_display_q_cols = st.multiselect(
                    "📋 表に表示する項目（クリックでON/OFFを切り替え）",
                    options=available_q_cols,
                    default=default_q_cols,
                    key="quiz_display_cols"
                )

            # 絞り込み
            df_q_filtered = df_quiz.copy()
            if len(q_date_range) == 2:
                df_q_filtered = df_q_filtered[(df_q_filtered['日時'].dt.date >= q_date_range[0]) & (df_q_filtered['日時'].dt.date <= q_date_range[1])]
            
            if selected_q_student != "すべて":
                search_q_name = selected_q_student.split(" - ")[1]
                df_q_filtered = df_q_filtered[df_q_filtered['生徒名'] == search_q_name]

            df_q_filtered['日時'] = df_q_filtered['日時'].dt.strftime('%Y/%m/%d')
            df_q_display = df_q_filtered.fillna("")

            # お留守番表示（Empty State）
            if df_q_display.empty:
                st.info("💡 指定された条件の小テスト記録は見つかりませんでした。\n日付の範囲を広げるか、別の生徒を選択してみてください。")
            else:
                st.success(f"該当記録: **{len(df_q_filtered)} 件**")
                if selected_display_q_cols:
                    st.dataframe(df_q_display[selected_display_q_cols], use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ 表示項目が何も選択されていません。項目を1つ以上選択してください。")