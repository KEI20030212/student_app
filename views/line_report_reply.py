import streamlit as st
import datetime
import pandas as pd
from utils.g_sheets import (
    save_parent_reply,
    get_student_master,
    get_all_teacher_names
)
from utils.api_guard import robust_api_call

# --- キャッシュ関数群 ---
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def safe_get_teacher_names():
    lst = robust_api_call(get_all_teacher_names, fallback_value=[])
    return list(lst)

# --- メイン描画関数 ---
def render_parent_reply_tab():
    st.write("LINE報告に対する保護者様からのリアクションや返信を記録し、信頼関係の見える化（ファン化分析）に活用します✨")
    
    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    teacher_names = safe_get_teacher_names() 
    
    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return

    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    
    selected_student = st.selectbox("👤 返信のあった生徒を選択してください", student_options, index=None, placeholder="-- 生徒を選択 --", key="parent_reply_student_select")
    
    if selected_student:
        student_id = selected_student.split(" - ")[0]
        student_name = selected_student.split(" - ")[1]
        
        with st.form(key="parent_reply_form", clear_on_submit=True):
            st.markdown(f"### 💬 {student_name} さんの保護者リアクション登録")
            
            c1, c2 = st.columns(2)
            with c1:
                target_date = st.date_input("📅 対象の授業日（報告書を送った日）", datetime.date.today())
            with c2:
                teacher_name = st.selectbox("👨‍🏫 報告書を作成した担当講師", teacher_names, index=None, placeholder="-- 講師を選択 --")
                
            reaction_type = st.selectbox(
                "🤝 保護者のリアクション・ファン化度評価",
                [
                    "🔥 大絶賛・大感謝（超ファン化・講習の提案やお知らせに即合意レベル）",
                    "🟢 好意的・納得（信頼構築・塾への指示通りに家庭が動く状態）",
                    "🟡 質問・相談あり（家庭との対話要フォロー・要社員共有）",
                    "🚨 悪印象・不満あり（至急のフォロー・面談要レベル）"
                ],
                index=1
            )
            
            reply_text = st.text_area(
                "📝 返信内容・特記事項（メモ）", 
                placeholder="実際の文面や、相談された内容の要約を入力してください。", 
                height=120
            )
            
            submit_reply = st.form_submit_button("🚀 保護者の返信記録をスプレッドシートへ保存する", use_container_width=True)
            
            if submit_reply:
                if not teacher_name:
                    st.error("⚠️ 担当講師を選択してください。")
                else:
                    with st.spinner("データを安全に書き込み中..."):
                        success = robust_api_call(
                            save_parent_reply,
                            date_str=target_date.strftime("%Y/%m/%d"),
                            student_id=student_id,
                            student_name=student_name,
                            teacher_name=teacher_name, 
                            reaction_type=reaction_type,
                            reply_text=reply_text,
                            fallback_value=False
                        )
                        if success:
                            st.toast(f"{student_name} さんの返信を記録しました！", icon="✅")
                        else:
                            st.error("❌ スプレッドシートへの保存に失敗しました。")