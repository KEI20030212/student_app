# views/test_scores_list.py

import streamlit as st
import pandas as pd
import datetime
import io
import re
import time
from utils.api_guard import robust_api_call

# データ取得用関数をインポート
from utils.g_sheets import (
    load_test_scores, 
    get_student_master,
    get_quiz_master_dict,                
    load_quiz_records,
    get_textbook_master,
    update_quiz_master_defaults  # 🌟 NEW: 追加した関数をインポート
)

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def safe_load_test_scores():
    return robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_quiz_details():
    return robust_api_call(get_quiz_master_dict, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_load_all_quizzes():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
  
@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    return robust_api_call(get_textbook_master, fallback_value={})


def render_test_scores_list_page():
    st.subheader("📝 成績・小テスト一覧")
    st.caption("定期テストや模試の成績一覧と、小テストの進捗マップをタブを切り替えて確認・ダウンロードできます。")

    # 1. 共通データの取得
    with st.spinner("データを読み込み中..."):
        df_tests = safe_load_test_scores()
        df_students = cached_get_student_master()
        df_all_quizzes = cached_load_all_quizzes()
        quiz_details = cached_get_quiz_details()
        textbook_master = cached_get_textbook_master()

    # 共通で使う「生徒の所属校舎・学年」の辞書を作成
    student_name_to_branch = {}
    student_name_to_grade = {}
    
    def assign_branch(s_id):
        s_id = str(s_id).lower()
        if s_id.startswith('t'): return "田端新町校"
        elif s_id.startswith('h'): return "東十条駅前校"
        elif s_id == "trial": return "体験授業"
        else: return "その他"

    if not df_students.empty and '生徒名' in df_students.columns and '生徒ID' in df_students.columns:
        for _, row in df_students.iterrows():
            s_name = str(row.get('生徒名', ""))
            student_name_to_branch[s_name] = assign_branch(row.get('生徒ID', ""))
            student_name_to_grade[s_name] = str(row.get('学年', "未設定"))

    # ==========================================
    # 🌟 画面を2つのタブに分割！
    # ==========================================
    tab_test, tab_quiz = st.tabs(["📝 定期テスト・模試・内申一覧", "📊 小テスト進捗 クラス全体マップ"])

    # ---------------------------------------------------------
    # タブ1: 定期テスト・模試・内申 成績一覧
    # ---------------------------------------------------------
    with tab_test:
        st.write("各テストの成績データを絞り込み、一覧表として確認・ダウンロードできます。")
        
        if df_tests.empty or "APIエラー発生" in df_tests.columns:
            st.error("成績データが取得できませんでした。")
        else:
            date_col = '実施日' if '実施日' in df_tests.columns else '日付' if '日付' in df_tests.columns else '日時' if '日時' in df_tests.columns else None
            name_col = '生徒名' if '生徒名' in df_tests.columns else '名前' if '名前' in df_tests.columns else None
            type_col = 'テスト種別' if 'テスト種別' in df_tests.columns else None
            test_name_col = 'テスト名' if 'テスト名' in df_tests.columns else None

            if not date_col or not name_col or not type_col:
                st.error("成績シートに必要な列（日時・生徒名・テスト種別）が見つかりません。")
            else:
                if not df_students.empty and name_col in df_tests.columns:
                    df_tests = pd.merge(df_tests, df_students[['生徒名', '学年', '生徒ID']], left_on=name_col, right_on='生徒名', how='left')
                    df_tests['所属校舎'] = df_tests['生徒ID'].apply(assign_branch)
                else:
                    df_tests['学年'] = "不明"
                    df_tests['所属校舎'] = "すべて"

                with st.container(border=True):
                    st.write("🔍 **絞り込み条件**")
                    c1, c2, c3, c4 = st.columns(4)
                    
                    branch_options = ["すべて"] + list(df_tests['所属校舎'].dropna().unique())
                    selected_branch = c1.selectbox("🏫 校舎", branch_options)
                    
                    grade_options = ["すべて"] + list(df_tests['学年'].dropna().unique())
                    selected_grade = c2.selectbox("🎯 学年", grade_options)
                    
                    type_options = ["すべて"] + list(df_tests[type_col].dropna().unique())
                    selected_type = c3.selectbox("📝 テスト種別", type_options)
                    
                    df_tests[date_col] = pd.to_datetime(df_tests[date_col], errors='coerce')
                    valid_dates = df_tests[date_col].dropna()
                    
                    if not valid_dates.empty:
                        min_date = valid_dates.min().date()
                        max_date = valid_dates.max().date()
                    else:
                        min_date = datetime.date(2020, 1, 1)
                        max_date = datetime.date.today()
                        
                    selected_date_range = c4.date_input(
                        "📅 実施期間 (開始日 〜 終了日)", 
                        value=(min_date, max_date),
                        min_value=datetime.date(2000, 1, 1),
                        max_value=datetime.date(2100, 12, 31)
                    )

                df_filtered = df_tests.copy()
                if selected_branch != "すべて": df_filtered = df_filtered[df_filtered['所属校舎'] == selected_branch]
                if selected_grade != "すべて": df_filtered = df_filtered[df_filtered['学年'] == selected_grade]
                if selected_type != "すべて": df_filtered = df_filtered[df_filtered[type_col] == selected_type]
                
                if isinstance(selected_date_range, (tuple, list)):
                    if len(selected_date_range) == 2:
                        start_date, end_date = selected_date_range
                        df_filtered = df_filtered[
                            (df_filtered[date_col].dt.date >= start_date) & 
                            (df_filtered[date_col].dt.date <= end_date)
                        ]
                    elif len(selected_date_range) == 1:
                        start_date = selected_date_range[0]
                        df_filtered = df_filtered[df_filtered[date_col].dt.date == start_date]

                if df_filtered.empty:
                    st.warning("指定された条件のデータはありません。")
                else:
                    df_filtered = df_filtered.sort_values(by=date_col, ascending=False)
                    df_filtered[date_col] = df_filtered[date_col].dt.strftime('%Y/%m/%d')

                    st.write(f"📊 **検索結果: {len(df_filtered)} 件**")
                    
                    base_cols = [date_col, '所属校舎', '学年', name_col, type_col]
                    if test_name_col: base_cols.append(test_name_col)
                    
                    all_possible_score_cols = [col for col in df_tests.columns if col not in base_cols and col not in ['生徒ID', '生徒名']]
                    
                    default_selected_cols = ['英語', '数学', '国語', '理科', '社会', '総合', '保体', '技術', '家庭', '美術', '音楽', '9科総合']
                    actual_default_cols = [col for col in default_selected_cols if col in all_possible_score_cols]

                    selected_score_cols = st.multiselect(
                        "👁️ 表示する成績データを選択（自由に付け外しできます）",
                        options=all_possible_score_cols,
                        default=actual_default_cols
                    )
                    
                    display_cols = base_cols + selected_score_cols
                    
                    df_display = df_filtered[display_cols].copy()
                    for col in df_display.columns:
                        df_display[col] = df_display[col].astype(str).replace(['nan', 'None', '<NA>'], '-')

                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                        df_display.to_excel(writer, index=False, sheet_name='成績一覧')
                    
                    safe_branch = re.sub(r'[\\/:*?"<>|]', '_', selected_branch)
                    safe_type = re.sub(r'[\\/:*?"<>|]', '_', selected_type)
                    file_name = f"{safe_branch}_{safe_type}_成績一覧.xlsx"

                    st.write("")
                    st.download_button(
                        label="📥 この一覧表をExcelでダウンロード",
                        data=excel_buffer.getvalue(),
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )

    # ---------------------------------------------------------
    # タブ2: 小テスト別 クラス全体マップ
    # ---------------------------------------------------------
    with tab_quiz:
        st.write("生徒の進捗・定着度マップを校舎ごとに確認・ダウンロードできます✨")

        if df_all_quizzes.empty or "APIエラー発生" in df_all_quizzes.columns:
            st.info("小テストの記録がまだありません。")
        else:
            taken_quizzes = [q for q in df_all_quizzes['テキスト'].dropna().unique().tolist() if q]
            
            # 🌟 シートの「E列」から現在のデフォルト候補を抽出
            default_candidates = set()
            for key, data in quiz_details.items():
                if data.get("is_default", False):
                    if "_" in key:
                        quiz_name = key.split("_", 1)[0]
                        default_candidates.add(quiz_name)
            
            valid_defaults = [q for q in default_candidates if q in taken_quizzes]
            
            # 🌟 アプリ画面からのデフォルト保存エリア
            c_sel, c_save = st.columns([4, 1.5], vertical_alignment="bottom")
            with c_sel:
                selected_quizzes_for_map = st.multiselect(
                    "📚 表示する小テストを選択（複数選択可）", 
                    taken_quizzes, 
                    default=valid_defaults,
                    placeholder="-- 小テストを選択 --",
                    key="active_quizzes_selection"
                )
            with c_save:
                # 権限がある管理者なら誰でも保存可能
                user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'guest'))).lower()
                if user_role in ['admin', 'owner', 'am']:
                    if st.button("💾 この選択をデフォルト保存", use_container_width=True, help="次回開いた時もこのテストが自動表示されます"):
                        with st.spinner("設定シートを更新中..."):
                            success = robust_api_call(update_quiz_master_defaults, selected_quizzes_for_map, fallback_value=False)
                            if success:
                                st.success("✅ デフォルト表示を更新しました！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ 更新に失敗しました。")
            
            if not selected_quizzes_for_map:
                st.info("👆 表示したい小テストを選択してください。")
            else:
                for selected_quiz_for_map in selected_quizzes_for_map:
                    st.markdown(f"### 🎯 【 {selected_quiz_for_map} 】の進捗マップ")
                    
                    df_q = df_all_quizzes[df_all_quizzes['テキスト'] == selected_quiz_for_map].copy()
                    df_q['点数'] = pd.to_numeric(df_q['点数'], errors='coerce')
                    df_q = df_q.dropna(subset=['点数']).copy()
                    
                    if df_q.empty:
                        st.info(f"【{selected_quiz_for_map}】の有効な点数記録がありません。")
                        st.divider()
                        continue
                        
                    df_q['校舎'] = df_q['名前'].map(lambda x: student_name_to_branch.get(x, "その他"))
                    
                    branch_order = ["田端新町校", "東十条駅前校", "体験授業", "その他"]
                    available_branches = [b for b in branch_order if b in df_q['校舎'].unique()]
                    
                    if not available_branches:
                        st.info("表示できる校舎データがありません。")
                        st.divider()
                        continue

                    map_tabs = st.tabs([f"🏫 {b}" for b in available_branches])
                    
                    def sort_key(c):
                        nums = re.findall(r'\d+', str(c))
                        return int(nums[0]) if nums else 999

                    def style_pivot_dataframe(pivot_df, target_q_name):
                        col_mapping = {}
                        t_master = textbook_master.get(target_q_name, {}) 
                        
                        for col in pivot_df.columns:
                            chap_str = str(col)
                            chap_name = t_master.get(chap_str, "")
                            if chap_name:
                                col_mapping[col] = f"{chap_str}: {chap_name}"
                            else:
                                col_mapping[col] = f"第{chap_str}回"
                                
                        pivot_df = pivot_df.rename(columns=col_mapping)

                        def add_icon(val):
                            if pd.isna(val) or val == "": return ""
                            
                            full_m = 100
                            matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{target_q_name}_")]
                            if matched_marks:
                                full_m = int(pd.Series(matched_marks).mode()[0])
                                    
                            try:
                                v = float(val)
                                ratio = v / full_m if full_m > 0 else 0
                                if ratio >= 1.0: return f"👑 {int(v)}"
                                elif ratio >= 0.85: return f"🟢 {int(v)}"
                                elif ratio >= 0.2: return f"🟡 {int(v)}"
                                else: return f"🔴 {int(v)}"
                            except:
                                return str(val)

                        styled_display = pivot_df.copy()
                        for col in styled_display.columns:
                            styled_display[col] = styled_display[col].apply(add_icon)

                        def color_bg(v):
                            if "👑" in str(v): return 'background-color: #fffacd; color: #000; font-weight: bold;'
                            if "🟢" in str(v): return 'background-color: #c6efce; color: #006100;'
                            if "🟡" in str(v): return 'background-color: #ffeb9c; color: #9c6500;'
                            if "🔴" in str(v): return 'background-color: #ffc7ce; color: #9c0006;'
                            return ''

                        try:
                            return styled_display.style.applymap(color_bg)
                        except AttributeError:
                            return styled_display.style.map(color_bg)
                    
                    for idx, branch in enumerate(available_branches):
                        with map_tabs[idx]:
                            df_branch = df_q[df_q['校舎'] == branch].copy()
                            
                            best_scores_all = df_branch.groupby(['名前', '単元'])['点数'].max().reset_index()
                            pivot_all = best_scores_all.pivot_table(
                                index='名前',
                                columns='単元',
                                values='点数',
                                aggfunc='max'
                            )
                            
                            if not pivot_all.empty:
                                pivot_all = pivot_all[sorted(pivot_all.columns.tolist(), key=sort_key)]
                                
                                pivot_all = pivot_all.reset_index()
                                pivot_all['学年'] = pivot_all['名前'].map(lambda x: student_name_to_grade.get(x, "未設定"))
                                
                                def get_grade_rank(g_str):
                                    mapping = {
                                        "小1": 1, "小2": 2, "小3": 3, "小4": 4, "小5": 5, "小6": 6,
                                        "中1": 7, "中2": 8, "中3": 9, "中１": 7, "中２": 8, "中３": 9,
                                        "高1": 10, "高2": 11, "高3": 12, "高１": 10, "高２": 11, "高３": 12
                                    }
                                    for k, v in mapping.items():
                                        if k in g_str: return v
                                    return 99
                                    
                                pivot_all['学年_ソート'] = pivot_all['学年'].apply(get_grade_rank)
                                pivot_all = pivot_all.sort_values(by=['学年_ソート', '名前'])
                                pivot_all = pivot_all.drop(columns=['学年_ソート'])
                                pivot_all = pivot_all.set_index(['学年', '名前'])
                                
                                styled_all_df = style_pivot_dataframe(pivot_all, selected_quiz_for_map)
                                st.dataframe(styled_all_df, use_container_width=True)
                                
                                excel_buffer_map = io.BytesIO()
                                with pd.ExcelWriter(excel_buffer_map, engine='xlsxwriter') as writer:
                                    styled_all_df.to_excel(writer, sheet_name=branch)
                                
                                excel_data_map = excel_buffer_map.getvalue()
                                safe_file_name_map = re.sub(r'[\\/:*?"<>|]', '_', selected_quiz_for_map)
                                
                                st.write("")
                                st.download_button(
                                    label=f"📥 この {branch} のマップをExcelでダウンロード",
                                    data=excel_data_map,
                                    file_name=f"{safe_file_name_map}_{branch}_全体マップ.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    type="primary",
                                    use_container_width=True,
                                    key=f"dl_map_{branch}_{selected_quiz_for_map}"
                                )
                            else:
                                st.info(f"この小テストを受けた {branch} の生徒はいません。")
                    st.divider()