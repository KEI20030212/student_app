import streamlit as st
import pandas as pd
from datetime import date
import time
from utils.g_sheets import update_homework_status
from utils.api_guard import robust_api_call

def render_hw_alert(df):
    st.write("「完了（終わった）」と「提出済（学校に出した）」を分けて管理します。")
    
    if df.empty or 'APIエラー発生' in df.columns:
        st.info("現在、登録されている学校の課題はありません。（または通信エラーによりデータを取得できませんでした）")
        return
        
    df_active = df[df["ステータス"] != "提出済"].copy()
    df_active["提出期限"] = pd.to_datetime(df_active["提出期限"], errors='coerce').dt.date
    df_active = df_active.dropna(subset=["提出期限"])
    
    if df_active.empty:
        st.success("✨ 現在、提出待ち（未完了）の課題はありません！みんなよく頑張っています。")
        return
        
    today = date.today()
    
    def get_priority(row):
        if row["ステータス"] == "完了": return 4
        days_left = (row["提出期限"] - today).days
        if days_left < 0: return 1
        elif days_left <= 2: return 2
        else: return 3

    df_active["優先度"] = df_active.apply(get_priority, axis=1)
    df_active = df_active.sort_values(["優先度", "提出期限"])
    students_ordered = df_active["生徒名"].drop_duplicates().tolist()

    for student in students_ordered:
        student_tasks = df_active[df_active["生徒名"] == student]
        worst_priority = student_tasks["優先度"].min()
        
        if worst_priority == 1: header_icon = "🔴 期限超過あり！"
        elif worst_priority == 2: header_icon = "🟡 期限直前あり"
        elif worst_priority == 4: header_icon = "🟦 提出待ち(すべて完了)"
        else: header_icon = "🟢 進行中"

        with st.expander(f"👤 {student} （未提出: {len(student_tasks)}件） - {header_icon}"):
            with st.form(key=f"form_student_{student}", border=False):
                update_targets = []
                for idx, row in student_tasks.iterrows():
                    days_left = (row["提出期限"] - today).days
                    if row["ステータス"] == "完了": status_label = "🟦 【提出確認】学校に出しましたか？"
                    elif days_left < 0: status_label = f"🔴 【期限超過！】 {abs(days_left)}日経過"
                    elif days_left <= 2: status_label = f"🟡 【期限直前】 あと{days_left}日"
                    else: status_label = f"🟢 あと{days_left}日"

                    col_t, col_s = st.columns([0.7, 0.3])
                    with col_t:
                        st.markdown(f"**【{row['教科']}】 {row['課題内容']}**")
                        st.caption(f"📅 期限: {row['提出期限']} | 📝 メモ: {row['メモ']} | {status_label}")
                    with col_s:
                        new_status = st.selectbox(
                            "ステータス", ["未着手", "進行中", "完了", "提出済"],
                            index=["未着手", "進行中", "完了", "提出済"].index(row["ステータス"]),
                            key=f"status_{idx}", label_visibility="collapsed" 
                        )
                        
                    update_targets.append({
                        "row_idx": row.name + 2, "old_status": row["ステータス"],
                        "new_status": new_status, "subject": row['教科']
                    })
                    if row.name != student_tasks.index[-1]:
                        st.divider()
                        
                if st.form_submit_button(f"💾 {student} さんの課題を一括更新", use_container_width=True):
                    with st.spinner(f"{student} さんのデータを更新中..."):
                        changed_count, error_count = 0, 0
                        for target in update_targets:
                            if target["old_status"] != target["new_status"]:
                                if robust_api_call(update_homework_status, target["row_idx"], target["new_status"]): changed_count += 1
                                else: error_count += 1
                                    
                        if changed_count > 0 and error_count == 0:
                            st.cache_data.clear() 
                            st.success(f"✅ {changed_count}件のステータスを更新しました！")
                            time.sleep(1.5)
                            st.rerun()
                        elif changed_count > 0 and error_count > 0:
                            st.cache_data.clear()
                            st.warning(f"⚠️ {changed_count}件更新、{error_count}件エラーが発生しました。")
                            time.sleep(2)
                            st.rerun()
                        elif error_count > 0:
                            st.error("❌ 通信エラーのため更新に失敗しました。")
                        else:
                            st.info("変更されたステータスはありませんでした。")