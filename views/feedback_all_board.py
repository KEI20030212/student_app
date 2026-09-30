import streamlit as st
import pandas as pd
import datetime # 🌟 NEW: 日付計算用に追加

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
        
    # 列を探す
    fb_col = 'AIフィードバック' if 'AIフィードバック' in df_logs.columns else (df_logs.columns[24] if len(df_logs.columns) > 24 else None)
    score_col = 'AIスコア' if 'AIスコア' in df_logs.columns else (df_logs.columns[25] if len(df_logs.columns) > 25 else None)
    teacher_col = '担当講師' if '担当講師' in df_logs.columns else None
    date_col = '日時' if '日時' in df_logs.columns else None
    student_col = '名前' if '名前' in df_logs.columns else ('生徒名' if '生徒名' in df_logs.columns else None)
    subject_col = '科目' if '科目' in df_logs.columns else None
    
    if not fb_col or not teacher_col or not student_col:
        st.warning("⚠️ フィードバック機能の準備中です。")
        return
        
    allowed_roles = ['admin', 'owner', 'am']
    is_admin = user_role in allowed_roles
    
    if is_admin:
        st.info("💡 ※管理者モードのため、全講師・全生徒のフィードバックを表示しています。")
        df_my_logs = df_logs.copy()
    else:
        df_my_logs = df_logs[df_logs[teacher_col] == teacher_name].copy()
        
    df_with_fb = df_my_logs.dropna(subset=[fb_col])
    df_with_fb = df_with_fb[df_with_fb[fb_col].astype(str).str.strip() != ""]
    df_with_fb = df_with_fb[~df_with_fb[fb_col].astype(str).str.contains("考え中", na=False)]
    
    if df_with_fb.empty:
        st.success("現在、表示できるフィードバック履歴はありません！")
        return
        
    # 🌟 日付処理を確実に行う
    if date_col:
        df_with_fb[date_col] = pd.to_datetime(df_with_fb[date_col], format='mixed', errors='coerce')
        # 変換できなかった日付（NaT）は、超過去の日付として扱うか除外する
        df_with_fb = df_with_fb.dropna(subset=[date_col])

    # ==========================================
    # 🌟 検索・絞り込みフィルター エリア
    # ==========================================
    with st.expander("🔍 フィードバックを絞り込む", expanded=False):
        
        # 🌟 NEW: 期間指定を1行目に配置（UI的に幅を取るため）
        today = datetime.date.today()
        default_start = today - datetime.timedelta(days=30) # デフォルトは過去30日
        
        sel_date_range = st.date_input(
            "📅 期間で絞り込み（開始日〜終了日）",
            value=(default_start, today),
            max_value=today
        )
        
        # 2行目に他のフィルターを配置
        c1, c2, c3 = st.columns(3)
        
        available_scores = df_with_fb[score_col].astype(str).str.strip().unique().tolist()
        available_scores = [s for s in available_scores if s and s != "nan"]
        available_scores.sort()
        sel_scores = c1.multiselect("🌟 AIスコアで絞り込み", options=available_scores, placeholder="すべてのスコアを表示")
        
        if is_admin:
            available_teachers = df_with_fb[teacher_col].astype(str).str.strip().unique().tolist()
            available_teachers = [t for t in available_teachers if t and t != "nan"]
            sel_teachers = c2.multiselect("👨‍🏫 担当講師で絞り込み", options=available_teachers, placeholder="すべての講師を表示")
        else:
            sel_teachers = [] 
            
        search_kw = c3.text_input("💬 キーワード検索", placeholder="例：宿題、遅刻、英単語...")

    # ==========================================
    # 🌟 フィルターの適用処理
    # ==========================================
    df_filtered = df_with_fb.copy()
    
    # 🌟 期間の絞り込み（date_input は (開始日, 終了日) のタプルを返す）
    if isinstance(sel_date_range, tuple) and len(sel_date_range) == 2:
        start_date = pd.to_datetime(sel_date_range[0])
        # 終了日は「その日の終わり（23:59:59）」まで含めるように調整
        end_date = pd.to_datetime(sel_date_range[1]) + pd.Timedelta(days=1, seconds=-1)
        df_filtered = df_filtered[(df_filtered[date_col] >= start_date) & (df_filtered[date_col] <= end_date)]
    elif isinstance(sel_date_range, tuple) and len(sel_date_range) == 1:
        # 開始日だけが選ばれていて、終了日が未選択の状態
        start_date = pd.to_datetime(sel_date_range[0])
        df_filtered = df_filtered[df_filtered[date_col] >= start_date]

    # スコアの絞り込み
    if sel_scores:
        df_filtered = df_filtered[df_filtered[score_col].astype(str).str.strip().isin(sel_scores)]
        
    # 講師の絞り込み
    if is_admin and sel_teachers:
        df_filtered = df_filtered[df_filtered[teacher_col].astype(str).str.strip().isin(sel_teachers)]
        
    # キーワードの絞り込み
    if search_kw:
        df_filtered = df_filtered[df_filtered[fb_col].astype(str).str.contains(search_kw, case=False, na=False)]

    st.divider()

    # 検索結果がゼロの場合の処理
    if df_filtered.empty:
        st.warning("指定された条件（期間・スコア・キーワード等）に一致するフィードバックは見つかりませんでした。条件を変えてお試しください。")
        return

    # ==========================================
    # 🌟 生徒ごとにアコーディオンを作成する処理（検索結果を表示）
    # ==========================================
    
    student_latest_date = df_filtered.groupby(student_col)[date_col].max().sort_values(ascending=False)
    
    st.write(f"🔍 検索結果: **{len(student_latest_date)} 名**（計 {len(df_filtered)} 件のフィードバック）")
    
    for student_name in student_latest_date.index:
        df_student = df_filtered[df_filtered[student_col] == student_name]
        
        if date_col:
            df_student = df_student.sort_values(date_col, ascending=False)
            
        record_count = len(df_student)
        
        with st.expander(f"👤 {student_name} さん （検索ヒット: {record_count}件）"):
            
            for _, row in df_student.iterrows():
                dt_val = row[date_col] if date_col else None
                ts = dt_val.strftime('%Y/%m/%d') if pd.notna(dt_val) else "日付不明"
                
                teacher = row[teacher_col]
                subj = row[subject_col] if subject_col else "-"
                score = str(row[score_col]).strip() if score_col else "-"
                comment = row[fb_col]
                
                if score == "S": score_badge = "🌟 **S**"
                elif score == "A": score_badge = "✨ **A**"
                elif score == "B": score_badge = "✅ **B**"
                elif score == "C": score_badge = "⚠️ **C**"
                else: score_badge = f"**{score}**"
                
                with st.container(border=True):
                    st.markdown(f"**🗓 {ts} | 📚 {subj} | 👨‍🏫 担当: {teacher} | 評価: {score_badge}**")
                    st.info(comment)