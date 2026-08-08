import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go  # 🌟 アイデア3：レーダーチャート用に追加！

def render_test_score_view(df_student_tests):
    """テスト成績推移・履歴の表示部分（最強アップグレード版）"""
    if df_student_tests.empty:
        st.info("まだ成績データがありません。")
        return

    # データの前処理
    df_view = df_student_tests.copy()
    df_view['日時'] = pd.to_datetime(df_view['日時'])
    df_view = df_view.sort_values('日時')

    # グラフ計算用に、文字列の点数("85"など)を数値に変換した列を裏で作る
    score_cols = ["英語", "数学", "国語", "理科", "社会", "総合"]
    for col in score_cols:
        if col in df_view.columns:
            df_view[col + "_num"] = pd.to_numeric(df_view[col], errors='coerce')

    st.subheader("📊 成績ダッシュボード")

    # ==========================================
    # 🌟 アイデア1 & 3：最新のKPIサマリー＆レーダーチャート
    # ==========================================
    df_regular = df_view[df_view['テスト種別'].isin(["定期テスト(中間など)", "期末テスト"])].copy()

    if len(df_regular) > 0:
        st.markdown("#### 🌟 最新の定期テスト結果")
        latest = df_regular.iloc[-1]
        prev = df_regular.iloc[-2] if len(df_regular) > 1 else None

        # 💡 アイデア1：パッと見ハイライト（KPI）
        metrics = [("英語", "英語_num"), ("数学", "数学_num"), ("国語", "国語_num"), 
                   ("理科", "理科_num"), ("社会", "社会_num"), ("総合", "総合_num")]
        
        m_cols = st.columns(6)
        for i, (label, col_name) in enumerate(metrics):
            if col_name in latest and pd.notna(latest[col_name]):
                val = int(latest[col_name])
                delta = None
                if prev is not None and col_name in prev and pd.notna(prev[col_name]):
                    delta = int(val - int(prev[col_name]))
                
                m_cols[i].metric(label=label, value=f"{val}点", delta=delta)

        st.write("") # スペース
        
        # 💡 アイデア3：レーダーチャート
        r_col1, r_col2 = st.columns([1.2, 1])
        with r_col1:
            categories = ['英語', '数学', '国語', '理科', '社会']
            scores = []
            for c in categories:
                v = latest.get(f"{c}_num")
                scores.append(v if pd.notna(v) else 0)
            
            # クモの巣を閉じるために最初の要素を末尾に追加
            scores.append(scores[0])
            cat_closed = categories + [categories[0]]
            
            fig = go.Figure(data=go.Scatterpolar(
                r=scores,
                theta=cat_closed,
                fill='toself',
                marker=dict(color='#FF4B4B'),
                name='最新成績'
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=False,
                margin=dict(l=30, r=30, t=20, b=20),
                height=280
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with r_col2:
            st.info(f"📅 **実施日**: {latest['日時'].strftime('%Y/%m/%d')}\n"
                    f"📝 **種別**: {latest['テスト種別']}\n\n"
                    "💡 **分析・面談のヒント**\n\n"
                    "緑色の数字（↑）は前回からの成長です！面談や声かけの際、まずはここを強く承認しましょう。\n\n"
                    "レーダーチャートがいびつな形（凹みがある）になっている科目は、重点的な対策や受講の追加提案のチャンスです。")
    else:
        st.info("定期テストのデータが登録されると、ここに成績サマリーとレーダーチャートが表示されます。")

    st.divider()

    # ==========================================
    # 🌟 アイデア2：テスト種別ごとのグラフ完全分離
    # ==========================================
    st.markdown("#### 📈 成績推移チャート")
    tab_reg, tab_mock, tab_nai = st.tabs(["🏫 定期テスト推移", "📝 外部模試・偏差値推移", "🔥 内申点・学習態度推移"])

    with tab_reg:
        if len(df_regular) > 0:
            plot_data = df_regular.set_index("日時")[["英語_num", "数学_num", "国語_num", "理科_num", "社会_num"]].dropna(how='all')
            if not plot_data.empty:
                plot_data.columns = ["英語", "数学", "国語", "理科", "社会"]
                st.line_chart(plot_data)
            else:
                st.caption("グラフ表示できる教科の点数がありません。")
        else:
            st.caption("定期テストのデータがありません。")

    with tab_mock:
        df_mock = df_view[df_view['テスト種別'] == "外部模試"].copy()
        if len(df_mock) > 0:
            st.markdown("**📉 5科偏差値 推移**")
            if '偏差値_5科' in df_mock.columns:
                df_mock['偏差値_5科_num'] = pd.to_numeric(df_mock['偏差値_5科'], errors='coerce')
                plot_dev = df_mock.set_index("日時")["偏差値_5科_num"].dropna()
                if not plot_dev.empty:
                    st.line_chart(plot_dev)
                else:
                    st.caption("偏差値のデータがありません。")
        else:
            st.caption("外部模試のデータがありません。")

    with tab_nai:
        df_naishin_only = df_view[df_view['テスト種別'] == "通知表（内申点）"].copy()
        
        if df_naishin_only.empty:
            st.caption("内申点・態度のデータがまだ登録されていません。")
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

    # ==========================================
    # 🌟 アイデア4：ヒートマップ化された成績履歴詳細
    # ==========================================
    st.markdown("#### 📋 成績履歴詳細（ヒートマップ）")
    
    # 画面表示用に、計算用の "_num" 列を除外して綺麗にする
    drop_cols = [c for c in df_view.columns if c.endswith("_num")]
    df_display = df_view.drop(columns=drop_cols).sort_values("日時", ascending=False)

    def color_score(val):
        """点数や態度に応じて背景色をつける魔法の関数"""
        # 数値（点数）の判定
        try:
            v = float(val)
            if v >= 80: return 'background-color: #d1e7dd; color: #0f5132; font-weight: bold;' # 🌟 青緑（高得点）
            if v < 50: return 'background-color: #f8d7da; color: #842029; font-weight: bold;'  # 🚨 赤（危険）
        except:
            pass
        
        # 文字（内申態度）の判定
        if val == 'A': return 'background-color: #d1e7dd; color: #0f5132;'
        if val == 'C': return 'background-color: #f8d7da; color: #842029;'
        return ''

    # 🌟 以前エラーログに出ていた「applymapの警告」も、最新の「map」に変更して修正済み！
    st.dataframe(
        df_display.style.map(color_score),
        hide_index=True,
        use_container_width=True
    )