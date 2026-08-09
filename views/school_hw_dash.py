import streamlit as st
import pandas as pd
from datetime import date

def render_hw_dash(df_dash):
    st.subheader("📊 生徒別の課題進捗状況")
    st.write("各生徒の課題消化率を棒グラフで確認できます。")
    
    if df_dash.empty or 'APIエラー発生' in df_dash.columns:
        st.info("現在、登録されている課題はありません。（または通信エラーにより取得できませんでした）")
        return
        
    # ==========================================
    # 🌟 追加：集計するテストを絞り込むフィルター
    # ==========================================
    # 古いデータでエラーが出ないよう、念のため空の列を補完
    for col in ['年度', '学期', 'テスト種別']:
        if col not in df_dash.columns:
            df_dash[col] = "未設定"
            
    st.markdown("##### 🔍 集計するテスト期間を選択")
    st.caption("選択したテストの課題だけを集計し、進捗率（分母）を計算します。")
    
    c1, c2, c3 = st.columns(3)
    
    # 選択肢の作成（空文字やnanは除外）
    years = ["すべて"] + sorted([str(y) for y in df_dash['年度'].unique() if str(y) != 'nan' and str(y).strip() != ""])
    terms = ["すべて"] + sorted([str(t) for t in df_dash['学期'].unique() if str(t) != 'nan' and str(t).strip() != ""])
    tests = ["すべて"] + sorted([str(t) for t in df_dash['テスト種別'].unique() if str(t) != 'nan' and str(t).strip() != ""])
    
    f_year = c1.selectbox("年度", years, index=0)
    f_term = c2.selectbox("学期", terms, index=0)
    f_test = c3.selectbox("テスト種別", tests, index=0)
    
    # 🌟 ここで指定した条件の課題だけを抽出（フィルター）！
    df_filtered = df_dash.copy()
    if f_year != "すべて":
        df_filtered = df_filtered[df_filtered['年度'].astype(str) == f_year]
    if f_term != "すべて":
        df_filtered = df_filtered[df_filtered['学期'] == f_term]
    if f_test != "すべて":
        df_filtered = df_filtered[df_filtered['テスト種別'] == f_test]
        
    st.divider()

    if df_filtered.empty:
        st.warning("選択した条件に一致する課題がありません。")
        return

    # ==========================================
    # 🌟 フィルターで絞り込まれたデータ（df_filtered）を使って計算！
    # ==========================================
    students_with_hw = sorted(df_filtered['生徒名'].unique())
    for student in students_with_hw:
        student_hw = df_filtered[df_filtered['生徒名'] == student]
        
        # 分母がテストごとの数に！
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