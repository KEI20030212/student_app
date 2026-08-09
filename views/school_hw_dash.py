import streamlit as st
import pandas as pd
from datetime import date

def render_hw_dash(df_dash):
    st.subheader("📊 生徒別の課題進捗状況")
    st.write("各生徒の課題消化率を棒グラフで確認できます。")
    
    if df_dash.empty or 'APIエラー発生' in df_dash.columns:
        st.info("現在、登録されている課題はありません。（または通信エラーにより取得できませんでした）")
        return
        
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