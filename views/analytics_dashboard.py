import streamlit as st
import pandas as pd
import re  # 👈 文字から数字を抜き出すためのツールを追加！
from utils.g_sheets import get_all_student_names, load_all_data

# --- 🌟 追加機能：「P.14~17」などからページ数を自動計算する関数 ---
def calculate_page_amount(text):
    if pd.isna(text): return 0
    text = str(text).strip()
    
    # パターン1：「14~17」や「14-17」のような範囲指定の場合
    match_range = re.search(r'(\d+)\s*[~〜\-]\s*(\d+)', text)
    if match_range:
        start = int(match_range.group(1))
        end = int(match_range.group(2))
        return max(0, end - start + 1) # 例: 14~17なら 17-14+1 = 4ページ
    
    # パターン2：単に「5」など数字だけ書かれている場合
    match_single = re.search(r'(\d+)', text)
    if match_single:
        return int(match_single.group(1))
    
    return 0


def render_analytics_dashboard_page():
    st.header("📊 講師パフォーマンス分析ダッシュボード")
    st.write("講師の「稼働状況」「指導の熱量」「宿題コントロール力」を可視化します。")

    # --- 列名の設定 ---
    report_col = 'アドバイス'
    hw_content_col = '次回の宿題ページ数'
    hw_status_col = 'やった宿題P'

    # 月の選択肢準備
    today = pd.Timestamp.now()
    default_months = [(today - pd.DateOffset(months=i)).strftime("%Y年%m月") for i in range(12)]
    df_all = pd.DataFrame()

    # 1. データ読み込み
    student_names = get_all_student_names()
    if not student_names:
        st.info("💡 生徒データが登録されていません。")
    else:
        all_data_list = []
        with st.spinner('全データを解析中... 先生たちのマネジメント力を集計しています！'):
            for s_name in student_names:
                df = load_all_data(s_name)
                if not df.empty:
                    df['生徒名'] = s_name
                    all_data_list.append(df)
        
        if all_data_list:
            df_all = pd.concat(all_data_list, ignore_index=True)
            df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
            df_all = df_all.dropna(subset=['日時'])
            df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

            # 熱量（文字数）の計算
            if report_col in df_all.columns:
                def count_chars(text):
                    if pd.isna(text): return 0
                    text_str = str(text).strip()
                    if text_str.lower() in ['nan', 'none', '<na>', '']: return 0
                    return len(text_str)
                df_all['報告文字数'] = df_all[report_col].apply(count_chars)

            # 宿題履行率の追跡ロジック
            if '科目' in df_all.columns and '担当講師' in df_all.columns:
                df_all = df_all.sort_values(by=['生徒名', '科目', '日時'])
                df_all['宿題を出した先生'] = df_all.groupby(['生徒名', '科目'])['担当講師'].shift(1)
                
                # 安全装置：列があるかチェック
                if hw_content_col in df_all.columns:
                    df_all['前回出された宿題内容'] = df_all.groupby(['生徒名', '科目'])[hw_content_col].shift(1)
                else:
                    df_all['前回出された宿題内容'] = None

    # 画面表示
    month_options = sorted(list(set(default_months + (df_all['年月'].unique().tolist() if not df_all.empty else []))), reverse=True)
    st.divider()
    selected_month = st.selectbox("📅 分析する月を選択", month_options)

    if df_all.empty or selected_month not in df_all['年月'].values:
        st.info(f"💡 {selected_month} の授業データはまだありません。")
        return

    df_month = df_all[df_all['年月'] == selected_month]
    teachers = [t for t in df_month['担当講師'].dropna().unique() if t not in ["未入力", ""]]
    
    selected_teacher = st.selectbox("👨‍🏫 分析する講師を選択", ["全員まとめて比較"] + teachers)
    st.divider()

    if selected_teacher == "全員まとめて比較":
        st.subheader(f"🏆 {selected_month} の全体ランキング")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📈 コマ数（授業回数）**")
            koma = df_month['担当講師'].value_counts().reset_index()
            koma.columns = ['講師名', 'コマ数']
            st.bar_chart(koma.set_index('講師名'))
        with c2:
            if '報告文字数' in df_month.columns:
                st.markdown("**🔥 アドバイスの平均文字数**")
                avg_chars = df_month.groupby('担当講師')['報告文字数'].mean().reset_index()
                st.bar_chart(avg_chars.set_index('担当講師'))
    else:
        # 個別分析
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("今月の担当コマ数", f"{len(df_t)} コマ")
        with col_b:
            if '報告文字数' in df_t.columns:
                st.metric("アドバイス平均文字数", f"{int(df_t['報告文字数'].mean())} 文字")

        st.divider()
        
        # --- 🌟 超進化した宿題コントロール力 分析 ---
        st.markdown(f"**📝 宿題量コントロール力（生徒のキャパシティ把握度）**")
        st.caption("※先生が出した宿題の合計ページ数に対して、生徒が実際に解いてきた合計ページ数の割合です。")
        
        # 該当データだけを抽出（警告回避のため .copy() を追加）
        df_hw_eval = df_month[
            (df_month['宿題を出した先生'] == selected_teacher) & 
            (df_month['前回出された宿題内容'].notna()) & 
            (df_month['前回出された宿題内容'] != "")
        ].copy()

        if not df_hw_eval.empty and hw_status_col in df_hw_eval.columns:
            # P.14~17 などを実際の「ページ数」に変換！
            df_hw_eval['出したページ数'] = df_hw_eval['前回出された宿題内容'].apply(calculate_page_amount)
            df_hw_eval['解いたページ数'] = df_hw_eval[hw_status_col].apply(calculate_page_amount)

            total_assigned = df_hw_eval['出したページ数'].sum()
            total_completed = df_hw_eval['解いたページ数'].sum()

            if total_assigned > 0:
                # 割合（パーセンテージ）を計算
                completion_rate = (total_completed / total_assigned) * 100
                
                # 3つの数値を並べて綺麗に表示
                col1, col2, col3 = st.columns(3)
                col1.metric("出した宿題の合計", f"{total_assigned} ページ")
                col2.metric("生徒が解いた合計", f"{total_completed} ページ")
                col3.metric("達成率 (完了/出した量)", f"{completion_rate:.1f} %")

                # バーで視覚的に表示（最大100%として表示）
                progress_val = min(completion_rate / 100, 1.0)
                st.progress(progress_val)
                
                # 先生へのフィードバックメッセージ！
                if completion_rate >= 90:
                    st.success("🌟 素晴らしい！生徒のキャパシティに合った適切な量の宿題が出せています！")
                elif completion_rate >= 70:
                    st.info("👍 おおむね良好です。一部の生徒にとって少し量が多いかもしれません。")
                else:
                    st.warning("⚠️ 達成率が低めです。宿題の量が多すぎるか、難易度が合っていない可能性があります。")
            else:
                st.info("数値として計算できる宿題データがありません。（例: 「14~17」や「5」などの数字が必要です）")
        else:
            st.info("宿題の達成状況データがまだありません。")