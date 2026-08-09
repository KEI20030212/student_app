import streamlit as st
import pandas as pd

def render_hw_past(df_hw, df_students):
    st.subheader("📜 過去のテスト課題・履歴検索")
    st.write("過去の定期テスト等で実際に出題された学校の課題範囲を検索し、来年以降の先回りテスト対策に活用できます！")

    if df_hw.empty or 'APIエラー発生' in df_hw.columns:
        st.info("検索できる過去の課題データがありません。")
        return
    if df_students.empty:
        st.warning("生徒データが読み込めません。")
        return
        
    for col in ['年度', '学期', 'テスト種別']:
        if col not in df_hw.columns: df_hw[col] = ""

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
                if total_tasks > 15: advice = "⚠️ **課題量が非常に多い傾向にあります。** テスト3週間前から塾での自習を声かけし、学校のワークの1周目を早めに終わらせるスケジュールを組みましょう。"
                elif total_tasks > 8: advice = "📊 **標準的な課題量です。** ただし直前に溜め込むと危険なため、通常授業内で少しずつ学校のワークを進めさせる指示を出してください。"
                else: advice = "🟢 **課題量は比較的少なめ（またはデータ蓄積中）です。** 学校の課題だけでなく、塾専用テキストを使った実践演習に時間を割いて得点アップを狙いましょう。"
                
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