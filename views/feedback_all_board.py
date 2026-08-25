import streamlit as st
import pandas as pd

from utils.g_sheets import get_all_logs
from utils.api_guard import robust_api_call

def safe_get_all_logs():
    df = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def render_feedback_all_board():
    teacher_name = st.session_state.get('username', '')
    user_role = st.session_state.get('role', '')
    
    st.subheader("📩 教室長（AI）からのフィードバック一覧")
    st.caption("生徒ごとに、これまでの指導報告に対するフィードバックをまとめて確認できます。今後の指導の参考にしてください！")
    
    with st.spinner("フィードバック履歴を読み込み中...🚀"):
        df_logs = safe_get_all_logs()
    
    if df_logs.empty or "APIエラー発生" in df_logs.columns:
        st.info("データが取得できませんでした。")
        return
        
    # 列を探す（強制インデックスフォールバック付きの安全設計）
    fb_col = 'AIフィードバック' if 'AIフィードバック' in df_logs.columns else (df_logs.columns[24] if len(df_logs.columns) > 24 else None)
    score_col = 'AIスコア' if 'AIスコア' in df_logs.columns else (df_logs.columns[25] if len(df_logs.columns) > 25 else None)
    teacher_col = '担当講師' if '担当講師' in df_logs.columns else None
    date_col = '日時' if '日時' in df_logs.columns else None
    student_col = '名前' if '名前' in df_logs.columns else ('生徒名' if '生徒名' in df_logs.columns else None)
    subject_col = '科目' if '科目' in df_logs.columns else None
    
    if not fb_col or not teacher_col or not student_col:
        st.warning("⚠️ フィードバック機能の準備中です。")
        return
        
    # 🌟 自分が担当した授業ログだけを抽出する
    allowed_roles = ['admin', 'owner', 'am']
    if user_role in allowed_roles:
        st.info("💡 ※管理者モードのため、全講師・全生徒のフィードバックを表示しています。")
        df_my_logs = df_logs.copy()
    else:
        df_my_logs = df_logs[df_logs[teacher_col] == teacher_name].copy()
        
    # FBが空欄、または「考え中...」のものを除外
    df_with_fb = df_my_logs.dropna(subset=[fb_col])
    df_with_fb = df_with_fb[df_with_fb[fb_col].astype(str).str.strip() != ""]
    df_with_fb = df_with_fb[~df_with_fb[fb_col].astype(str).str.contains("考え中", na=False)]
    
    if df_with_fb.empty:
        st.success("現在、表示できるフィードバック履歴はありません！")
        return
        
    # 日付をDatetime型に変換（並び替えのため）
    if date_col:
        df_with_fb[date_col] = pd.to_datetime(df_with_fb[date_col], format='mixed', errors='coerce')
        
    # ==========================================
    # 🌟 生徒ごとにアコーディオンを作成する処理
    # ==========================================
    
    # 最近フィードバックがあった生徒から順番に上から表示するための並び替え
    student_latest_date = df_with_fb.groupby(student_col)[date_col].max().sort_values(ascending=False)
    
    # 生徒ごとにグループ化して表示
    for student_name in student_latest_date.index:
        # その生徒のフィードバック履歴だけを抽出
        df_student = df_with_fb[df_with_fb[student_col] == student_name]
        
        # 新しい日付順（最新の授業が一番上）に並べる
        if date_col:
            df_student = df_student.sort_values(date_col, ascending=False)
            
        record_count = len(df_student)
        
        # 🌟 生徒ごとのアコーディオン（開閉メニュー）を作成
        with st.expander(f"👤 {student_name} さん （履歴: {record_count}件）"):
            
            # その生徒の履歴を1件ずつカード化して表示
            for _, row in df_student.iterrows():
                dt_val = row[date_col] if date_col else None
                ts = dt_val.strftime('%Y/%m/%d') if pd.notna(dt_val) else "日付不明"
                
                teacher = row[teacher_col]
                subj = row[subject_col] if subject_col else "-"
                score = str(row[score_col]).strip() if score_col else "-"
                comment = row[fb_col]
                
                # スコアに応じたミニバッジを作成
                if score == "S": score_badge = "🌟 **S**"
                elif score == "A": score_badge = "✨ **A**"
                elif score == "B": score_badge = "✅ **B**"
                elif score == "C": score_badge = "⚠️ **C**"
                else: score_badge = f"**{score}**"
                
                # 履歴カードを描画
                with st.container(border=True):
                    st.markdown(f"**🗓 {ts} | 📚 {subj} | 👨‍🏫 担当: {teacher} | 評価: {score_badge}**")
                    st.info(comment)