import streamlit as st
import pandas as pd
import re  
# 🌟 変更: 小テストデータも一括で読み込むために load_quiz_records を追加
from utils.g_sheets import get_all_logs, load_quiz_records
from utils.api_guard import robust_api_call

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

# 🌟 全データを一括取得するキャッシュ関数
@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

# 🌟 小テストデータを一括取得するキャッシュ関数を追加
@st.cache_data(ttl=60)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

def render_analytics_dashboard_page():
    st.header("📊 講師パフォーマンス分析ダッシュボード")
    st.write("講師の「稼働状況」「指導の熱量」「宿題コントロール力」「小テスト実施率」を可視化します。")

    # --- 列名の設定 ---
    report_col = 'アドバイス'
    hw_content_col = '次回の宿題ページ数'
    
    # 統合シートの列名「やった宿題P」に合わせる
    hw_status_col = 'やった宿題P' 

    # 月の選択肢準備
    today = pd.Timestamp.now()
    default_months = [(today - pd.DateOffset(months=i)).strftime("%Y年%m月") for i in range(12)]
    
    # 1. データ一括読み込み (授業記録と小テスト記録)
    with st.spinner('全データを解析中... 先生たちのマネジメント力を集計しています！（超高速🚀）'):
        df_all = cached_get_all_logs()
        df_quiz = cached_load_quiz_records()
        
    if df_all.empty or "APIエラー発生" in df_all.columns:
        st.info("💡 授業データが登録されていないか、通信エラーで取得できませんでした。")
        return

    # 🌟 名前列の統一（「生徒名」と「名前」の揺れを吸収）
    if '名前' in df_all.columns:
        if '生徒名' in df_all.columns:
            df_all = df_all.drop(columns=['名前'])
        else:
            df_all = df_all.rename(columns={'名前': '生徒名'})

    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['日付'] = df_all['日時'].dt.date # 🌟 照合用の「日付」列を作成
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    # ==========================================
    # 🌟 小テスト実施データの照合ロジック
    # ==========================================
    if not df_quiz.empty and "APIエラー発生" not in df_quiz.columns:
        if '名前' in df_quiz.columns:
            df_quiz = df_quiz.rename(columns={'名前': '生徒名'})
        
        df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
        df_quiz['日付'] = df_quiz['日時'].dt.date
        
        # 同じ日に同じ生徒が小テストを受けていれば「実施した」とみなす
        quiz_done = df_quiz[['日付', '生徒名']].drop_duplicates()
        quiz_done['小テスト実施'] = True
    else:
        quiz_done = pd.DataFrame(columns=['日付', '生徒名', '小テスト実施'])

    # 授業記録に「小テスト実施フラグ」を結合
    df_all = df_all.merge(quiz_done, on=['日付', '生徒名'], how='left')
    df_all['小テスト実施'] = df_all['小テスト実施'].fillna(False)

    # 熱量（文字数）の計算
    if report_col in df_all.columns:
        def count_chars(text):
            if pd.isna(text): return 0
            text_str = str(text).strip()
            if text_str.lower() in ['nan', 'none', '<na>', '']: return 0
            return len(text_str)
        df_all['報告文字数'] = df_all[report_col].apply(count_chars)

    # 宿題履行率の追跡ロジック
    if '科目' in df_all.columns and '担当講師' in df_all.columns and '生徒名' in df_all.columns:
        df_all = df_all.sort_values(by=['生徒名', '科目', '日時'])
        df_all['宿題を出した先生'] = df_all.groupby(['生徒名', '科目'])['担当講師'].shift(1)
        
        if hw_content_col in df_all.columns:
            df_all['前回出された宿題内容'] = df_all.groupby(['生徒名', '科目'])[hw_content_col].shift(1)
        else:
            df_all['前回出された宿題内容'] = None
            
        if hw_status_col not in df_all.columns and 'やった宿題' in df_all.columns:
            hw_status_col = 'やった宿題'

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
        # 🌟 3列に変更して小テスト実施率を追加
        c1, c2, c3 = st.columns(3)
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
        with c3:
            st.markdown("**💯 小テスト実施率 (%)**")
            # 講師ごとにTrueの割合を出すことで実施率を計算
            quiz_rates = df_month.groupby('担当講師')['小テスト実施'].mean().reset_index()
            quiz_rates['実施率(%)'] = quiz_rates['小テスト実施'] * 100
            st.bar_chart(quiz_rates.set_index('担当講師')['実施率(%)'])
            
    else:
        # 個別分析
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        # 🌟 3列に変更してサマリーにも表示
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("今月の担当コマ数", f"{len(df_t)} コマ")
        with col_b:
            if '報告文字数' in df_t.columns:
                st.metric("アドバイス平均文字数", f"{int(df_t['報告文字数'].mean())} 文字")
        with col_c:
            t_quiz_rate = int(df_t['小テスト実施'].mean() * 100) if len(df_t) > 0 else 0
            st.metric("小テスト実施率", f"{t_quiz_rate} %")

        st.divider()
        
        # --- 🌟 超進化した宿題コントロール力 分析 ---
        st.markdown(f"**📝 宿題量コントロール力（生徒のキャパシティ把握度）**")
        st.caption("※先生が出した宿題の合計ページ数に対して、生徒が実際に解いてきた合計ページ数の割合です。")
        
        df_hw_eval = df_month[
            (df_month['宿題を出した先生'] == selected_teacher) & 
            (df_month['前回出された宿題内容'].notna()) & 
            (df_month['前回出された宿題内容'] != "")
        ].copy()

        if not df_hw_eval.empty and hw_status_col in df_hw_eval.columns:
            df_hw_eval['出したページ数'] = df_hw_eval['前回出された宿題内容'].apply(calculate_page_amount)
            df_hw_eval['解いたページ数'] = df_hw_eval[hw_status_col].apply(calculate_page_amount)

            total_assigned = df_hw_eval['出したページ数'].sum()
            total_completed = df_hw_eval['解いたページ数'].sum()

            if total_assigned > 0:
                completion_rate = (total_completed / total_assigned) * 100
                
                col1, col2, col3 = st.columns(3)
                col1.metric("出した宿題の合計", f"{total_assigned} ページ")
                col2.metric("生徒が解いた合計", f"{total_completed} ページ")
                col3.metric("達成率 (完了/出した量)", f"{completion_rate:.1f} %")

                progress_val = min(completion_rate / 100, 1.0)
                st.progress(progress_val)
                
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

        st.divider()

        # --- 🌟 小テスト実施率 分析 ---
        st.markdown(f"**💯 小テスト実施率（定着度の計測）**")
        st.caption("※担当した全授業のうち、小テストを実施してシステムに記録した授業の割合です。")
        
        col_q1, col_q2, col_q3 = st.columns(3)
        total_classes = len(df_t)
        quiz_done_count = df_t['小テスト実施'].sum()
        q_rate = (quiz_done_count / total_classes * 100) if total_classes > 0 else 0
        
        col_q1.metric("担当コマ数", f"{total_classes} コマ")
        col_q2.metric("小テスト実施コマ", f"{quiz_done_count} コマ")
        col_q3.metric("実施率", f"{q_rate:.1f} %")
        
        st.progress(min(q_rate / 100, 1.0))

        if q_rate >= 80:
            st.success("🌟 素晴らしい！授業の定着度を毎回しっかり計測できています！")
        elif q_rate >= 50:
            st.info("👍 半数以上の授業でテストを実施できています。")
        else:
            st.warning("⚠️ 実施率が低めです。授業の冒頭で小テストを行い、結果を記録するルーティンを徹底しましょう。")