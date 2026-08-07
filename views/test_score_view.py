import streamlit as st
import pandas as pd
import altair as alt

def render_test_score_view(df_student_tests):
    """テスト成績推移・履歴の表示部分"""
    if not df_student_tests.empty:
        df_view = df_student_tests.copy()
        df_view['日時'] = pd.to_datetime(df_view['日時'])
        df_view = df_view.sort_values('日時')

        st.subheader("📊 成績・内申・態度 推移チャート")

        view_mode = st.radio("表示項目を選択してください", ["総合点・偏差値", "内申点・学習態度"], horizontal=True)

        if view_mode == "総合点・偏差値":
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📈 総合点 推移**")
                df_total = df_view[df_view['総合'] != "-"]
                if not df_total.empty:
                    st.line_chart(df_total.set_index("日時")["総合"])
                else:
                    st.caption("総合点のデータがありません。")

            with col2:
                st.markdown("**📉 5科偏差値 推移**")
                df_dev = df_view[df_view['偏差値_5科'] != "-"]
                if not df_dev.empty:
                    st.line_chart(df_dev.set_index("日時")["偏差値_5科"])
                else:
                    st.caption("偏差値のデータがありません。")

        else:  
            df_naishin_only = df_view[df_view['テスト種別'] == "通知表（内申点）"].copy()
            
            if df_naishin_only.empty:
                st.info("内申点・態度のデータがまだ登録されていません。")
            else:
                subjects = ["英語", "数学", "国語", "理科", "社会", "保体", "技家", "美術", "音楽"]
                selected_subs = st.multiselect("表示する科目を選択", subjects, default=["英語", "数学", "国語"])

                col_n, col_a = st.columns(2)

                with col_n:
                    st.markdown("**🏫 内申点(1-5) 推移**")
                    plot_data_n = pd.DataFrame({"日時": df_naishin_only["日時"]})
                    for sub in selected_subs:
                        col_name = f"{sub} 内申"
                        if col_name in df_naishin_only.columns:
                            plot_data_n[sub] = pd.to_numeric(df_naishin_only[col_name], errors='coerce')
                    
                    st.line_chart(plot_data_n.set_index("日時"))

                with col_a:
                    st.markdown("**🔥 学習態度(A-C) 推移**")
                    st.caption("※ A=3, B=2, C=1 として計算")
                    
                    att_map = {"A": 3, "B": 2, "C": 1}
                    plot_data_a = pd.DataFrame({"日時": df_naishin_only["日時"]})
                    
                    for sub in selected_subs:
                        col_name = f"{sub} 態度"
                        if col_name in df_naishin_only.columns:
                            plot_data_a[sub] = df_naishin_only[col_name].map(att_map)
                    
                    chart_a = alt.Chart(plot_data_a.melt("日時", var_name="科目", value_name="値")).mark_line(point=True).encode(
                        x='日時:T',
                        y=alt.Y('値:Q', scale=alt.Scale(domain=[1, 3]), axis=alt.Axis(values=[1, 2, 3], labelExpr="datum.value == 3 ? 'A' : datum.value == 2 ? 'B' : 'C'")),
                        color='科目:N',
                        tooltip=['日時', '科目', '値']
                    ).properties(height=300)
                    st.altair_chart(chart_a, use_container_width=True)

        st.divider()
        st.subheader("📋 成績履歴詳細")
        
        def color_attitude(val):
            if val == 'A': return 'background-color: #d1e7dd'
            if val == 'C': return 'background-color: #f8d7da'
            return ''

        st.dataframe(
            df_view.sort_values("日時", ascending=False),
            hide_index=True,
            use_container_width=True
        )
        
    else:
        st.info("まだ成績データがありません。")