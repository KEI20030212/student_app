import streamlit as st
import pandas as pd
from datetime import date, datetime
import time

from utils.g_sheets import (
    load_school_homework_data, 
    update_homework_status, 
    add_school_homework_multi, 
    get_student_master,
    update_school_homework_detail 
)

from utils.api_guard import robust_api_call

def render_school_homework_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🎒 学校課題管理")
    with col_r:
        if st.button("🔄 情報を更新"):
            st.cache_data.clear() 
            st.rerun()
            
    # 🌟 タブを5つに拡張！
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録", "📊 進捗ダッシュボード", "🛠️ 課題の修正・管理", "📜 過去の課題・履歴検索"])

    # ==========================================
    # タブ1：アラート・進捗更新
    # ==========================================
    with tab1:
        st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
        
        df = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
        
        if df.empty or 'APIエラー発生' in df.columns:
            st.info("現在、登録されている学校の課題はありません。（または通信エラーによりデータを取得できませんでした）")
        else:
            df_active = df[df["ステータス"] != "提出済"].copy()
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"], errors='coerce').dt.date
            df_active = df_active.dropna(subset=["提出期限"])

            today = date.today()

            def get_priority(row):
                if row["ステータス"] == "完了":
                    return 4  # すでに終わっているものは一番下
                
                days_left = (row["提出期限"] - today).days
                if days_left < 0:
                    return 1  # 🔥 期限超過
                elif days_left <= 2:
                    return 2  # 🚨 期限直前
                else:
                    return 3  # 🟢 まだ余裕あり

            df_active["優先度"] = df_active.apply(get_priority, axis=1)
            df_active = df_active.sort_values(["優先度", "提出期限"])

            students_ordered = df_active["生徒名"].drop_duplicates().tolist()

            for student in students_ordered:
                student_tasks = df_active[df_active["生徒名"] == student]
                
                worst_priority = student_tasks["優先度"].min()
                if worst_priority == 1:
                    header_icon = "🔴 期限超過あり！"
                elif worst_priority == 2:
                    header_icon = "🟡 期限直前あり"
                elif worst_priority == 4:
                    header_icon = "🟦 提出待ち(すべて完了)"
                else:
                    header_icon = "🟢 進行中"

                with st.expander(f"👤 {student} （未提出: {len(student_tasks)}件） - {header_icon}"):
                    # 🌟 変更ポイント：生徒まるごと1つのフォームにする！
                    with st.form(key=f"form_student_{student}", border=False):
                        update_targets = []
                        
                        for idx, row in student_tasks.iterrows():
                            days_left = (row["提出期限"] - today).days
                            
                            if row["ステータス"] == "完了":
                                status_label = "🟦 【提出確認】学校に出しましたか？"
                            elif days_left < 0:
                                status_label = f"🔴 【期限超過！】 {abs(days_left)}日経過"
                            elif days_left <= 2:
                                status_label = f"🟡 【期限直前】 あと{days_left}日"
                            else:
                                status_label = f"🟢 あと{days_left}日"

                            col_t, col_s = st.columns([0.7, 0.3])
                            with col_t:
                                st.markdown(f"**【{row['教科']}】 {row['課題内容']}**")
                                st.caption(f"📅 期限: {row['提出期限']} | 📝 メモ: {row['メモ']} | {status_label}")
                            
                            with col_s:
                                new_status = st.selectbox(
                                    "ステータス", 
                                    ["未着手", "進行中", "完了", "提出済"],
                                    index=["未着手", "進行中", "完了", "提出済"].index(row["ステータス"]),
                                    key=f"status_{idx}",
                                    label_visibility="collapsed" 
                                )
                                
                            # 現在のステータスと、選択されたステータスを記憶
                            update_targets.append({
                                "row_idx": row.name + 2,
                                "old_status": row["ステータス"],
                                "new_status": new_status,
                                "subject": row['教科']
                            })
                            
                            if row.name != student_tasks.index[-1]:
                                st.divider()
                                
                        # 🌟 フォームの一番下に「一括更新」ボタンを設置
                        submitted = st.form_submit_button(f"💾 {student} さんの課題を一括更新", use_container_width=True)
                        
                        if submitted:
                            with st.spinner(f"{student} さんのデータを更新中..."):
                                changed_count = 0
                                error_count = 0
                                
                                for target in update_targets:
                                    # 🌟 変更があった課題だけを裏側で更新処理する（無駄な通信を削減）
                                    if target["old_status"] != target["new_status"]:
                                        success = robust_api_call(update_homework_status, target["row_idx"], target["new_status"])
                                        if success:
                                            changed_count += 1
                                        else:
                                            error_count += 1
                                            
                                if changed_count > 0 and error_count == 0:
                                    st.cache_data.clear() 
                                    st.success(f"✅ {changed_count}件のステータスを更新しました！")
                                    time.sleep(1.5)
                                    st.rerun()
                                elif changed_count > 0 and error_count > 0:
                                    st.cache_data.clear()
                                    st.warning(f"⚠️ {changed_count}件更新しましたが、{error_count}件エラーが発生しました。")
                                    time.sleep(2)
                                    st.rerun()
                                elif error_count > 0:
                                    st.error("❌ 通信エラーのため更新に失敗しました。時間をおいて再試行してください。")
                                else:
                                    st.info("変更されたステータスはありませんでした。")

    # ==========================================
    # タブ2：学校 × 学年 での一括登録
    # ==========================================
    with tab2:
        st.subheader("➕ 学校・学年を指定して一括登録")
        st.info("課題内容を改行して入力すると、一度に複数の課題を登録できます。")
        
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        
        if df_students.empty:
            st.warning("生徒データが取得できません。通信エラーか、設定_生徒情報シートを確認してください。")
        else:
            if '学校名' in df_students.columns:
                valid_schools = sorted([s for s in df_students['学校名'].unique() if str(s).strip() != ""])
            else:
                st.error("「設定_生徒情報」シートに「学校名」列が見つかりません。")
                return

            if '学年' in df_students.columns:
                valid_grades = sorted([g for g in df_students['学年'].unique() if str(g).strip() != ""])
            else:
                valid_grades = []
            
            with st.form("simple_add_form"):
                
                current_year = date.today().year
                if date.today().month < 4:
                    current_year -= 1
                
                st.markdown("##### 📅 時期・テスト設定")
                c_y, c_t, c_k = st.columns(3)
                with c_y:
                    nendo = st.number_input("年度", value=current_year, step=1)
                with c_t:
                    gakki = st.selectbox("学期", ["1学期", "2学期", "3学期", "前期", "後期", "夏休み", "冬休み", "春休み", "その他"])
                with c_k:
                    test_type = st.selectbox("期間・種別", ["中間テスト", "期末テスト", "実力テスト", "課題テスト", "長期休み課題", "その他"])
                
                st.divider()
                st.markdown("##### 🏫 ターゲット設定")
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    target_school = st.selectbox("🏫 対象の学校名", valid_schools)
                with col_f2:
                    target_grade = st.selectbox("🎯 対象の学年", valid_grades)
                
                target_student_list = df_students[
                    (df_students['学校名'] == target_school) & 
                    (df_students['学年'] == target_grade)
                ]['生徒名'].tolist()
                
                st.write(f"💡 **対象生徒:** {', '.join(target_student_list) if target_student_list else '該当者なし'}")
                st.divider()
                
                col1, col2 = st.columns(2)
                with col1:
                    subject = st.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "音楽", "美術", "保体", "技家", "その他"])
                with col2:
                    deadline = st.date_input("提出期限", date.today())
                
                content_text = st.text_area(
                    "課題内容 (1行に1つずつ入力してください)",
                    placeholder="数学ワーク P10-P20\n計算プリント No.5\n英単語テストの練習"
                )
                
                memo = st.text_area("メモ (全課題に共通して保存されます)")
                
                submitted = st.form_submit_button("一括登録する！", use_container_width=True)
                
                if submitted:
                    task_list = [t.strip() for t in content_text.split("\n") if t.strip()]
                    
                    if not target_student_list:
                        st.error(f"{target_school}の{target_grade}に該当する生徒がいません。")
                    elif not task_list:
                        st.error("課題内容を1つ以上入力してください！")
                    else:
                        with st.spinner("一括登録中..."):
                            result = robust_api_call(
                                add_school_homework_multi, 
                                nendo, gakki, test_type, target_student_list, subject, task_list, deadline, memo,
                                fallback_value=(False, "通信エラーが発生しました。時間を置いてお試しください。")
                            )
                            is_success, error_msg = result
                            
                            if is_success:
                                st.success(f"【{target_school} {target_grade}】の{len(target_student_list)}名に、{len(task_list)}個の課題を登録しました！")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"登録失敗: {error_msg}")

    # ==========================================
    # タブ3：📊 進捗ダッシュボード
    # ==========================================
    with tab3:
        st.subheader("📊 生徒別の課題進捗状況")
        st.write("各生徒の課題消化率を棒グラフで確認できます。")
        
        df_dash = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
        
        if df_dash.empty or 'APIエラー発生' in df_dash.columns:
            st.info("現在、登録されている課題はありません。（または通信エラーにより取得できませんでした）")
        else:
            students_with_hw = sorted(df_dash['生徒名'].unique())
            
            for student in students_with_hw:
                student_hw = df_dash[df_dash['生徒名'] == student]
                
                total_hw = len(student_hw)
                completed_hw = len(student_hw[student_hw['ステータス'] == '完了'])
                submitted_hw = len(student_hw[student_hw['ステータス'] == '提出済'])
                
                done_hw = completed_hw + submitted_hw
                
                progress_rate = done_hw / total_hw if total_hw > 0 else 0
                progress_percent = int(progress_rate * 100)
                
                star = "✨ 完璧！" if progress_percent == 100 else ""
                
                st.write(f"#### 👤 {student} （{done_hw} / {total_hw} 完了） **{progress_percent}%** {star}")
                st.progress(progress_rate)
                
                unfinished_hw = student_hw[~student_hw['ステータス'].isin(['完了', '提出済'])]
                if not unfinished_hw.empty:
                    with st.expander("📝 残りの課題を見る"):
                        for _, row in unfinished_hw.iterrows():
                            try:
                                dl_date = pd.to_datetime(row["提出期限"]).date()
                                days_left = (dl_date - date.today()).days
                                warning = f"🚨(期限まで{days_left}日)" if days_left <= 3 else ""
                            except:
                                warning = ""
                            
                            st.write(f"- 【{row['教科']}】 {row['課題内容']} {warning} （現在の状態: {row['ステータス']}）")
                st.divider()

    # ==========================================
    # タブ4：🛠️ 課題の修正・管理
    # ==========================================
    with tab4:
        st.subheader("🛠️ 登録済み課題の修正")
        st.write("登録済みの課題内容や提出期限を後から修正できます。")
        
        df_hw = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        
        if df_hw.empty or 'APIエラー発生' in df_hw.columns:
            st.info("修正できる課題データがありません。")
        elif df_students.empty:
            st.warning("生徒データが読み込めません。")
        else:
            for col in ['年度', '学期', 'テスト種別']:
                if col not in df_hw.columns:
                    df_hw[col] = ""
                    
            df_merged = pd.merge(df_hw, df_students[['生徒名', '学校名', '学年']], on='生徒名', how='left')
            
            st.markdown("##### 🔍 絞り込み条件")
            c_f1, c_f2 = st.columns(2)
            f_school = c_f1.selectbox("🏫 学校名", ["すべて"] + sorted([s for s in df_merged['学校名'].unique() if str(s) != 'nan' and str(s).strip() != ""]), key="f_sch")
            f_grade = c_f2.selectbox("🎯 学年", ["すべて"] + sorted([g for g in df_merged['学年'].unique() if str(g) != 'nan' and str(g).strip() != ""]), key="f_grd")
            
            c_f3, c_f4 = st.columns(2)
            f_term = c_f3.selectbox("📅 学期", ["すべて"] + sorted([t for t in df_merged['学期'].unique() if str(t) != 'nan' and str(t).strip() != ""]), key="f_term")
            f_test = c_f4.selectbox("🔥 テスト種別", ["すべて"] + sorted([t for t in df_merged['テスト種別'].unique() if str(t) != 'nan' and str(t).strip() != ""]), key="f_test")
            
            filtered_df = df_merged.copy()
            if f_school != "すべて": filtered_df = filtered_df[filtered_df['学校名'] == f_school]
            if f_grade != "すべて": filtered_df = filtered_df[filtered_df['学年'] == f_grade]
            if f_term != "すべて": filtered_df = filtered_df[filtered_df['学期'] == f_term]
            if f_test != "すべて": filtered_df = filtered_df[filtered_df['テスト種別'] == f_test]
            
            st.divider()
            
            if filtered_df.empty:
                st.info("条件に一致する課題は見つかりませんでした。")
            else:
                students_in_filter = sorted(filtered_df['生徒名'].unique())
                st.success(f"条件に一致する生徒が {len(students_in_filter)}名 見つかりました。アコーディオンを開いて編集してください。")
                
                for student in students_in_filter:
                    student_tasks = filtered_df[filtered_df['生徒名'] == student]
                    
                    with st.expander(f"👤 {student} の課題を修正（{len(student_tasks)}件）", expanded=False):
                        for idx, row in student_tasks.iterrows():
                            with st.container(border=True):
                                with st.form(key=f"edit_form_{idx}", border=False):
                                    c_e1, c_e2, c_e3 = st.columns([2, 3, 2])
                                    edit_subj = c_e1.text_input("教科", value=row.get('教科', ''), key=f"e_subj_{idx}")
                                    edit_task = c_e2.text_input("課題内容", value=row.get('課題内容', ''), key=f"e_task_{idx}")
                                    
                                    try:
                                        def_date = pd.to_datetime(row.get('提出期限')).date()
                                    except:
                                        def_date = date.today()
                                    edit_dead = c_e3.date_input("提出期限", value=def_date, key=f"e_dead_{idx}")
                                    
                                    c_e4, c_e5 = st.columns([4, 1])
                                    edit_memo = c_e4.text_input("メモ", value=row.get('メモ', ''), key=f"e_memo_{idx}")
                                    
                                    submitted_edit = c_e5.form_submit_button("💾 保存", use_container_width=True)
                                    
                                    if submitted_edit:
                                        with st.spinner("更新中..."):
                                            success = robust_api_call(
                                                update_school_homework_detail,
                                                row.name + 2, 
                                                edit_subj, edit_task, edit_dead, edit_memo,
                                                fallback_value=False
                                            )
                                            if success:
                                                st.success("✅ 更新しました！")
                                                st.cache_data.clear()
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error("❌ 更新エラー")

    # ==========================================
    # 🌟 新設タブ5：📜 過去の課題・履歴検索
    # ==========================================
    with tab5:
        st.subheader("📜 過去のテスト課題・履歴検索")
        st.write("過去の定期テスト等で実際に出題された学校の課題範囲を検索し、来年以降の先回りテスト対策に活用できます！")

        df_hw = robust_api_call(load_school_homework_data, fallback_value=pd.DataFrame())
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())

        if df_hw.empty or 'APIエラー発生' in df_hw.columns:
            st.info("検索できる過去の課題データがありません。")
        elif df_students.empty:
            st.warning("生徒データが読み込めません。")
        else:
            # 古いデータにも対応できるように空の列を補完
            for col in ['年度', '学期', 'テスト種別']:
                if col not in df_hw.columns:
                    df_hw[col] = ""

            df_merged = pd.merge(df_hw, df_students[['生徒名', '学校名', '学年']], on='生徒名', how='left')

            st.markdown("##### 🔍 過去データの検索条件")
            
            with st.form("search_past_hw_form"):
                c_s1, c_s2, c_s3 = st.columns(3)
                search_school = c_s1.selectbox("🏫 学校名", ["すべて"] + sorted([s for s in df_merged['学校名'].unique() if str(s) != 'nan' and str(s).strip() != ""]))
                search_grade = c_s2.selectbox("🎯 学年", ["すべて"] + sorted([g for g in df_merged['学年'].unique() if str(g) != 'nan' and str(g).strip() != ""]))
                search_term = c_s3.selectbox("📅 学期", ["すべて"] + sorted([t for t in df_merged['学期'].unique() if str(t) != 'nan' and str(t).strip() != ""]))

                c_s4, c_s5 = st.columns([1, 2])
                search_test = c_s4.selectbox("🔥 テスト種別", ["すべて"] + sorted([t for t in df_merged['テスト種別'].unique() if str(t) != 'nan' and str(t).strip() != ""]))
                search_subj = c_s5.selectbox("📖 教科", ["すべて"] + sorted([s for s in df_merged['教科'].unique() if str(s) != 'nan' and str(s).strip() != ""]))

                search_clicked = st.form_submit_button("🔍 この条件で過去の課題を検索する", type="primary", use_container_width=True)

            if search_clicked:
                st.divider()
                
                with st.spinner("過去のデータを整理中..."):
                    # フィルタリング実行
                    filtered_df = df_merged.copy()
                    if search_school != "すべて": filtered_df = filtered_df[filtered_df['学校名'] == search_school]
                    if search_grade != "すべて": filtered_df = filtered_df[filtered_df['学年'] == search_grade]
                    if search_term != "すべて": filtered_df = filtered_df[filtered_df['学期'] == search_term]
                    if search_test != "すべて": filtered_df = filtered_df[filtered_df['テスト種別'] == search_test]
                    if search_subj != "すべて": filtered_df = filtered_df[filtered_df['教科'] == search_subj]

                    if filtered_df.empty:
                        st.info("条件に一致する過去の課題データは見つかりませんでした。")
                    else:
                        unique_tasks = filtered_df.drop_duplicates(subset=['教科', '課題内容']).copy()
                        
                        st.success(f"📚 条件に一致する過去の課題が **{len(unique_tasks)}件** 見つかりました！")

                        total_tasks = len(unique_tasks)
                        st.markdown("##### 💡 塾長・教室長への教務アドバイス（自動分析）")
                        if total_tasks > 15:
                            advice = "⚠️ **課題量が非常に多い傾向にあります。** テスト3週間前から塾での自習を声かけし、学校のワークの1周目を早めに終わらせるスケジュールを組みましょう。"
                        elif total_tasks > 8:
                            advice = "📊 **標準的な課題量です。** ただし直前に溜め込むと危険なため、通常授業内で少しずつ学校のワークを進めさせる指示を出してください。"
                        else:
                            advice = "🟢 **課題量は比較的少なめ（またはデータ蓄積中）です。** 学校の課題だけでなく、塾専用テキストを使った実践演習に時間を割いて得点アップを狙いましょう。"
                        
                        st.info(advice)
                        st.write("")

                        subjects = unique_tasks['教科'].unique()
                        for subj in subjects:
                            st.markdown(f"#### 📘 【{subj}】の過去課題リスト")
                            subj_tasks = unique_tasks[unique_tasks['教科'] == subj]
                            
                            for _, row in subj_tasks.iterrows():
                                memo_text = f"（メモ: {row['メモ']}）" if str(row['メモ']) != 'nan' and str(row['メモ']).strip() != "" else ""
                                st.write(f"- {row['課題内容']} {memo_text}")
                            st.write("")