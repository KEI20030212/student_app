import streamlit as st
import pandas as pd
import datetime

from utils.g_sheets import load_parent_reply_data, get_student_master, get_all_teacher_names
from utils.api_guard import robust_api_call

# --- データ取得用関数（二重キャッシュ防止のため表側はキャッシュなし） ---
def get_reply_data():
    return robust_api_call(load_parent_reply_data, fallback_value=pd.DataFrame())

def get_student_list():
    df = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
    if not df.empty and '生徒名' in df.columns:
        return df['生徒名'].dropna().unique().tolist()
    return []

def get_teacher_list():
    lst = robust_api_call(get_all_teacher_names, fallback_value=[])
    return list(lst)

def render_parent_reply_dashboard():
    st.header("💬 保護者リアクション検索ダッシュボード")
    st.write("LINE報告に対する保護者様からの過去のリアクションを、タイムライン形式で一覧表示・検索できる画面です。")
    
    # データの読み込み
    with st.spinner("リアクション履歴を読み込み中..."):
        df_replies = get_reply_data()
        
    if df_replies.empty or "APIエラー発生" in df_replies.columns:
        st.warning("保護者からのリアクション記録がまだないか、データの取得に失敗しました。")
        return

    # カラム名の揺れを吸収して標準化
    date_col = '授業日' if '授業日' in df_replies.columns else ('日付' if '日付' in df_replies.columns else '日時')
    name_col = '生徒名' if '生徒名' in df_replies.columns else '名前'
    teacher_col = '担当講師' if '担当講師' in df_replies.columns else '講師'
    reaction_col = '評価' if '評価' in df_replies.columns else ('リアクション' if 'リアクション' in df_replies.columns else 'リアクション種別')
    text_col = '内容' if '内容' in df_replies.columns else ('返信内容' if '返信内容' in df_replies.columns else '返信メモ')

    # 日付型に変換
    df_replies[date_col] = pd.to_datetime(df_replies[date_col], errors='coerce')
    df_replies = df_replies.dropna(subset=[date_col])
    
    # 降順（新しい順）に並べ替え
    df_replies = df_replies.sort_values(by=date_col, ascending=False)

    # ==========================================
    # 🔍 絞り込みフィルター（案2の要素）
    # ==========================================
    with st.container(border=True):
        st.markdown("##### 🔍 絞り込み検索")
        
        c1, c2 = st.columns(2)
        
        # 1. 期間フィルター
        min_date = df_replies[date_col].min().date()
        max_date = df_replies[date_col].max().date()
        selected_dates = c1.date_input(
            "📅 期間を選択",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        # 2. リアクション（評価）フィルター
        all_reactions = df_replies[reaction_col].dropna().unique().tolist()
        selected_reactions = c2.multiselect(
            "🤝 評価（リアクション）で絞り込み",
            options=all_reactions,
            default=[],
            placeholder="すべて表示（選択すると絞り込まれます）"
        )
        
        c3, c4 = st.columns(2)
        
        # 3. 担当講師フィルター
        teacher_opts = get_teacher_list()
        selected_teachers = c3.multiselect(
            "👨‍🏫 担当講師で絞り込み",
            options=teacher_opts,
            default=[],
            placeholder="すべて表示"
        )
        
        # 4. 生徒名フィルター
        student_opts = get_student_list()
        selected_students = c4.multiselect(
            "👤 生徒名で絞り込み",
            options=student_opts,
            default=[],
            placeholder="すべて表示"
        )

    # ==========================================
    # ⚙️ フィルタリング実行
    # ==========================================
    df_filtered = df_replies.copy()

    if len(selected_dates) == 2:
        start_date, end_date = selected_dates
        df_filtered = df_filtered[
            (df_filtered[date_col].dt.date >= start_date) & 
            (df_filtered[date_col].dt.date <= end_date)
        ]
        
    if selected_reactions:
        df_filtered = df_filtered[df_filtered[reaction_col].isin(selected_reactions)]
        
    if selected_teachers:
        df_filtered = df_filtered[df_filtered[teacher_col].isin(selected_teachers)]
        
    if selected_students:
        df_filtered = df_filtered[df_filtered[name_col].isin(selected_students)]

    st.write("")
    
    # ==========================================
    # 📱 タイムライン表示（案1の要素）
    # ==========================================
    if df_filtered.empty:
        st.info("💡 指定された条件に一致するリアクション記録はありません。")
    else:
        st.success(f"該当するリアクション: **{len(df_filtered)} 件**")
        st.divider()
        
        for _, row in df_filtered.iterrows():
            d_val = row[date_col].strftime('%Y/%m/%d')
            s_val = row.get(name_col, "不明")
            t_val = row.get(teacher_col, "不明")
            r_val = row.get(reaction_col, "不明")
            text_val = row.get(text_col, "")
            
            # 評価に応じてカードの色味（境界線など）を変える工夫
            border_color = "gray"
            if "🔥" in str(r_val) or "大絶賛" in str(r_val):
                emoji = "🔥"
            elif "🟢" in str(r_val) or "好意的" in str(r_val):
                emoji = "🟢"
            elif "🟡" in str(r_val) or "質問" in str(r_val):
                emoji = "🟡"
            elif "🚨" in str(r_val) or "悪印象" in str(r_val):
                emoji = "🚨"
            else:
                emoji = "💬"

            # カード風コンテナで出力
            with st.container(border=True):
                st.markdown(f"### {emoji} {s_val} さん")
                st.caption(f"**📅 授業日:** {d_val} ｜ **👨‍🏫 報告者:** {t_val} 先生")
                
                st.markdown(f"**評価:** {r_val}")
                
                if str(text_val).strip() and str(text_val) != "nan":
                    # テキストエリアの内容を見やすく表示
                    st.info(str(text_val).replace('\n', '  \n'))
                else:
                    st.write("（コメントなし）")