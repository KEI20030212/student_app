import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
from utils.g_sheets import (
    load_school_homework_data, 
    update_homework_status, 
    add_school_homework_multi, 
    get_all_student_grades
)

def render_school_homework_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("🎒 学校課題管理")
    with col_r:
        if st.button("🔄 情報を更新"):
            load_school_homework_data.clear()
            st.rerun()
            
    tab1, tab2, tab3 = st.tabs(["📋 提出アラート・進捗更新", "➕ 課題の一括登録", "📊 進捗ダッシュボード"])

    # ==========================================
    # タブ1：アラート・進捗更新（🔥生徒ごとにまとめる版）
    # ==========================================
    with tab1:
        st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
        df = load_school_homework_data()
        
        if df.empty:
            st.info("現在、登録されている学校の課題はありません。")
        else:
            df_active = df[df["ステータス"] != "提出済"].copy()
            df_active["提出期限"] = pd.to_datetime(df_active["提出期限"], errors='coerce').dt.date
            df_active = df_active.dropna(subset=["提出期限"])

            today = date.today()

            # 優先度（ヤバさ）を計算するロジック
            def get_priority(row):
                if row["ステータス"] == "完了":
                    return 4  # すでに終わっているものは一番下（あとは出すだけ）
                
                days_left = (row["提出期限"] - today).days
                if days_left < 0:
                    return 1  # 🔥 期限超過（最優先で対応！）
                elif days_left <= 2:
                    return 2  # 🚨 期限直前（今日・明日・明後日）
                else:
                    return 3  # 🟢 まだ余裕あり

            df_active["優先度"] = df_active.apply(get_priority, axis=1)
            # まず全課題をヤバい順に並び替え
            df_active = df_active.sort_values(["優先度", "提出期限"])

            # 🌟 新機能：生徒ごとにグループ化するためのリストを作成
            # （すでにヤバい順に並んでいるので、ここで上から順に生徒名を拾えば「一番ヤバい課題を抱えている生徒」が上に来ます）
            students_ordered = df_active["生徒名"].drop_duplicates().tolist()

            # 生徒ごとに折りたたみ（Expander）を作成
            for student in students_ordered:
                # その生徒の課題だけを抽出
                student_tasks = df_active[df_active["生徒名"] == student]
                
                # その生徒が抱えている一番ヤバい優先度を取得して、タイトルのアイコンを決定
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
                    # その生徒の各課題を表示
                    for idx, row in student_tasks.iterrows():
                        days_left = (row["提出期限"] - today).days
                        
                        # 個別課題のラベル設定
                        if row["ステータス"] == "完了":
                            status_label = "🟦 【提出確認】学校に出しましたか？"
                        elif days_left < 0:
                            status_label = f"🔴 【期限超過！】 {abs(days_left)}日経過"
                        elif days_left <= 2:
                            status_label = f"🟡 【期限直前】 あと{days_left}日"
                        else:
                            status_label = f"🟢 あと{days_left}日"

                        # 見た目をスッキリさせるためのレイアウト
                        st.markdown(f"**【{row['教科']}】 {row['課題内容']}**")
                        st.caption(f"📅 期限: {row['提出期限']} | 📝 メモ: {row['メモ']} | {status_label}")
                        
                        col_s, col_b = st.columns([0.7, 0.3])
                        with col_s:
                            new_status = st.selectbox(
                                "ステータス", 
                                ["未着手", "進行中", "完了", "提出済"],
                                index=["未着手", "進行中", "完了", "提出済"].index(row["ステータス"]),
                                key=f"status_{idx}",
                                label_visibility="collapsed" # ラベルを隠してスッキリ見せる
                            )
                        with col_b:
                            if st.button("💾 更新", key=f"btn_{idx}", use_container_width=True):
                                with st.spinner("反映中..."):
                                    if update_homework_status(row.name + 2, new_status):
                                        load_school_homework_data.clear()
                                        time.sleep(1.5)
                                        st.success(f"{row['教科']}の状況を更新しました！")
                                        st.rerun()
                        
                        # 最後の課題以外は区切り線を引く
                        if row.name != student_tasks.index[-1]:
                            st.divider()

    # ==========================================
    # タブ2：学校 × 学年 での一括登録
    # ==========================================
    with tab2:
        st.subheader("➕ 学校・学年を指定して一括登録")
        st.info("課題内容を改行して入力すると、一度に複数の課題を登録できます。")
        
        df_students = get_all_student_grades()
        
        if df_students.empty:
            st.warning("生徒データが取得できません。設定_生徒情報シートを確認してください。")
        else:
            if '学校名' in df_students.columns:
                valid_schools = sorted([s for s in df_students['学校名'].unique() if str(s).strip() != ""])
            else:
                st.error("「設定_生徒情報」シートに「学校名」列が見つかりません。")
                return

            valid_grades = sorted([g for g in df_students['学年'].unique() if str(g).strip() != ""])
            
            with st.form("simple_add_form"):
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
                            is_success, error_msg = add_school_homework_multi(
                                target_student_list, subject, task_list, deadline, memo
                            )
                            if is_success:
                                st.success(f"【{target_school} {target_grade}】の{len(target_student_list)}名に、{len(task_list)}個の課題を登録しました！")
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
        
        df_dash = load_school_homework_data()
        
        if df_dash.empty:
            st.info("現在、登録されている課題はありません。")
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