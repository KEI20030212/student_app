import streamlit as st
import pandas as pd

from utils.g_sheets import get_all_logs
from utils.api_guard import robust_api_call

def safe_get_all_logs():
    df = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

def render_feedback_board():
    # 今ログインしている人の情報を取得
    teacher_name = st.session_state.get('username', '')
    user_role = st.session_state.get('role', '')
    
    st.subheader("📩 教室長（AI）からのフィードバック")
    st.caption("あなたが作成した指導報告書に対するフィードバックです。今後の指導の参考にしてください！")
    
    df_logs = safe_get_all_logs()
    
    if df_logs.empty or "APIエラー発生" in df_logs.columns:
        st.info("データが取得できませんでした。")
        return
        
    # 列を探す（もし名前が違っても、インデックス24と25で強制的に探す安全設計）
    fb_col = 'AIフィードバック' if 'AIフィードバック' in df_logs.columns else (df_logs.columns[24] if len(df_logs.columns) > 24 else None)
    score_col = 'AIスコア' if 'AIスコア' in df_logs.columns else (df_logs.columns[25] if len(df_logs.columns) > 25 else None)
    teacher_col = '担当講師' if '担当講師' in df_logs.columns else None
    date_col = '日時' if '日時' in df_logs.columns else None
    student_col = '名前' if '名前' in df_logs.columns else ('生徒名' if '生徒名' in df_logs.columns else None)
    
    if not fb_col or not teacher_col:
        st.warning("⚠️ フィードバック機能の準備中です。（スプレッドシートのY列1行目に「AIフィードバック」、Z列に「AIスコア」と入力してください）")
        return
        
    # 🌟 自分が担当した授業ログだけを抽出する（管理者の場合は全員分を表示！）
    if user_role in ['admin', 'owner', 'head_teacher']:
        st.info("※管理者モードのため、全講師の最新フィードバックをまとめて表示しています。")
        df_my_logs = df_logs.copy()
    else:
        df_my_logs = df_logs[df_logs[teacher_col] == teacher_name].copy()
        
    # FBが空欄（まだ書かれていない）ものを除外
    df_with_fb = df_my_logs.dropna(subset=[fb_col])
    df_with_fb = df_with_fb[df_with_fb[fb_col].astype(str).str.strip() != ""]
    
    if df_with_fb.empty:
        st.success("現在、あなた宛ての新しいフィードバックはありません！")
        return
        
    # 新しい日付順に並べ替え
    if date_col:
        df_with_fb[date_col] = pd.to_datetime(df_with_fb[date_col], format='mixed', errors='coerce')
        df_with_fb = df_with_fb.sort_values(date_col, ascending=False)
        
    # 最新の10件だけを表示（画面が長くなりすぎるのを防ぐ）
    df_recent_fb = df_with_fb.head(10)
    
    # 🌟 FBカードを1件ずつ描画する
    for _, row in df_recent_fb.iterrows():
        dt_val = row[date_col] if date_col else None
        ts = dt_val.strftime('%Y/%m/%d') if pd.notna(dt_val) else "不明な日時"
        
        student = row[student_col] if student_col else "不明な生徒"
        teacher = row[teacher_col]
        score = str(row[score_col]).strip() if score_col else "-"
        comment = row[fb_col]
        
        # スコアに応じたバッジを作成
        if score == "S": score_badge = "🌟 **評価: S** (素晴らしいレポートです！)"
        elif score == "A": score_badge = "✨ **評価: A** (良いレポートです！)"
        elif score == "B": score_badge = "✅ **評価: B**"
        elif score == "C": score_badge = "⚠️ **評価: C** (もう少し具体的に書いてみましょう)"
        else: score_badge = f"**評価: {score}**"
        
        # 枠線付きのカードで綺麗に表示
        with st.container(border=True):
            st.markdown(f"**🗓 {ts} | 👤 生徒: {student} | 👨‍🏫 担当: {teacher}**")
            st.markdown(score_badge)
            st.info(comment)