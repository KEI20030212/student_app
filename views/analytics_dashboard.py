import streamlit as st
import pandas as pd
import re  
from utils.g_sheets import get_all_logs, load_quiz_records, load_parent_reply_data
from utils.api_guard import robust_api_call

def calculate_page_amount(text):
    if pd.isna(text): return 0
    text = str(text).strip()
    match_range = re.search(r'(\d+)\s*[~〜\-]\s*(\d+)', text)
    if match_range:
        start = int(match_range.group(1))
        end = int(match_range.group(2))
        return max(0, end - start + 1)
    match_single = re.search(r'(\d+)', text)
    if match_single:
        return int(match_single.group(1))
    return 0

def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_load_quiz_records():
    return robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def cached_load_parent_reply_data():
    return robust_api_call(load_parent_reply_data, fallback_value=pd.DataFrame())

def render_analytics_dashboard_page():
    col_h, col_r = st.columns([0.8, 0.2])
    with col_h:
        st.header("📊 講師パフォーマンス分析ダッシュボード")
    with col_r:
        if st.button("🔄 データを更新", use_container_width=True):
            st.cache_data.clear() 
            st.rerun()            

    st.write("講師の「稼働状況」「指導の熱量」「宿題コントロール力」「小テスト実施率」「保護者ファン化度」を可視化します。")

    report_col = 'アドバイス'
    hw_content_col = '次回の宿題ページ数'
    hw_status_col = 'やった宿題P' 

    today = pd.Timestamp.now()
    default_months = [(today - pd.DateOffset(months=i)).strftime("%Y年%m月") for i in range(12)]
    
    with st.spinner('全データを解析中... 先生たちのマネジメント力を集計しています！（超高速🚀）'):
        df_all_raw = cached_get_all_logs()
        df_all = df_all_raw.copy()
        df_quiz = cached_load_quiz_records()
        df_reply = cached_load_parent_reply_data() 
        
    if df_all.empty or "APIエラー発生" in df_all.columns:
        st.info("💡 授業データが登録されていないか、通信エラーで取得できませんでした。")
        return

    if '名前' in df_all.columns:
        if '生徒名' in df_all.columns:
            df_all = df_all.drop(columns=['名前'])
        else:
            df_all = df_all.rename(columns={'名前': '生徒名'})

    df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
    df_all = df_all.dropna(subset=['日時'])
    df_all['日付'] = df_all['日時'].dt.date 
    df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")

    # --- 小テストデータの照合 ---
    if not df_quiz.empty and "APIエラー発生" not in df_quiz.columns:
        if '名前' in df_quiz.columns: df_quiz = df_quiz.rename(columns={'名前': '生徒名'})
        df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
        df_quiz['日付'] = df_quiz['日時'].dt.date
        quiz_done = df_quiz[['日付', '生徒名']].drop_duplicates()
        quiz_done['小テスト実施'] = True
    else:
        quiz_done = pd.DataFrame(columns=['日付', '生徒名', '小テスト実施'])

    df_all = df_all.merge(quiz_done, on=['日付', '生徒名'], how='left')
    df_all['小テスト実施'] = df_all['小テスト実施'].fillna(False)

    # --- 保護者リアクションの結合 ---
    if not df_reply.empty and "APIエラー発生" not in df_reply.columns:
        required_cols = ['授業日', '生徒名', '担当講師', 'リアクション種別']
        if all(col in df_reply.columns for col in required_cols):
            df_reply['授業日'] = pd.to_datetime(df_reply['授業日'], format='mixed', errors='coerce').dt.date
            reply_clean = df_reply[['授業日', '生徒名', '担当講師', 'リアクション種別']].copy()
            reply_clean.columns = ['日付', '生徒名', '担当講師', '保護者リアクション']
            reply_clean = reply_clean.drop_duplicates(subset=['日付', '生徒名', '担当講師'])
        else:
            reply_clean = pd.DataFrame(columns=['日付', '生徒名', '担当講師', '保護者リアクション'])
    else:
        reply_clean = pd.DataFrame(columns=['日付', '生徒名', '担当講師', '保護者リアクション'])

    df_all = df_all.merge(reply_clean, on=['日付', '生徒名', '担当講師'], how='left')
    df_all['保護者リアクション'] = df_all['保護者リアクション'].fillna("🔵 既読スルー（自動カウント）")

    # 熱量計算
    if report_col in df_all.columns:
        def count_chars(text):
            if pd.isna(text): return 0
            text_str = str(text).strip()
            if text_str.lower() in ['nan', 'none', '<na>', '']: return 0
            return len(text_str)
        df_all['報告文字数'] = df_all[report_col].apply(count_chars)

    # 宿題履行率
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
            quiz_rates = df_month.groupby('担当講師')['小テスト実施'].mean().reset_index()
            quiz_rates['実施率(%)'] = quiz_rates['小テスト実施'] * 100
            st.bar_chart(quiz_rates.set_index('担当講師')['実施率(%)'])
            
        st.write("")
        st.markdown("### 💬 講師別：保護者のリアクション比率（ファン化度グラフ）")
        st.caption("※「既読スルー（自動カウント）」は除外し、実際にアクションがあったものだけを表示しています。")
        
        df_react_only = df_month[df_month['保護者リアクション'] != "🔵 既読スルー（自動カウント）"]
        
        # 🌟 修正：リアクションが1件でも存在する場合のみピボット集計を実行（ValueError防止ガード）
        if not df_react_only.empty:
            df_pivot = pd.crosstab(df_react_only['担当講師'], df_react_only['保護者リアクション'])
            
            for t in teachers:
                if t not in df_pivot.index:
                    df_pivot.loc[t] = 0
                    
            df_pivot = df_pivot.loc[[t for t in df_pivot.index if t in teachers]]
            st.bar_chart(df_pivot, stack=True)
        else:
            st.info("💡 選択された月には、「既読スルー」以外の保護者リアクションがまだ記録されていません。")
            
    else:
        # 個別分析
        st.subheader(f"👩‍🏫 {selected_teacher} 先生の分析レポート")
        df_t = df_month[df_month['担当講師'] == selected_teacher]

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("今月の担当コマ数", f"{len(df_t)} コマ")
        with col_b:
            if '報告文字数' in df_t.columns:
                st.metric("アドバイス平均文字数", f"{int(df_t['報告文字数'].mean())} 文字")
        with col_c:
            t_quiz_rate = int(df_t['小テスト実施'].mean() * 100) if len(df_t) > 0 else 0
            st.metric("小テスト実施率", f"{t_quiz_rate} %")
        with col_d:
            star_count = df_t['保護者リアクション'].str.contains("大絶賛").sum()
            star_rate = int((star_count / len(df_t)) * 100) if len(df_t) > 0 else 0
            st.metric("🔥 神対応・大絶賛率", f"{star_rate} %")

        st.divider()
        
        # --- 宿題コントロール力 分析 ---
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
                st.progress(min(completion_rate / 100, 1.0))
                
                if completion_rate >= 90: st.success("🌟 素晴らしい！生徒のキャパシティに合った適切な量の宿題が出せています！")
                elif completion_rate >= 70: st.info("👍 おおむね良好です。一部の生徒にとって少し量が多いかもしれません。")
                else: st.warning("⚠️ 達成率が低めです。宿題の量が多すぎるか、難易度が合っていない可能性があります。")
            else:
                st.info("数値として計算できる宿題データがありません。")
        else:
            st.info("宿題の達成状況データがまだありません。")

        st.divider()

        # --- 小テスト実施率 分析 ---
        st.markdown(f"**💯 小テスト実施率（定着度の計測）**")
        col_q1, col_q2, col_q3 = st.columns(3)
        total_classes = len(df_t)
        quiz_done_count = df_t['小テスト実施'].sum()
        q_rate = (quiz_done_count / total_classes * 100) if total_classes > 0 else 0
        col_q1.metric("担当コマ数", f"{total_classes} コマ")
        col_q2.metric("小テスト実施コマ", f"{quiz_done_count} コマ")
        col_q3.metric("実施率", f"{q_rate:.1f} %")
        st.progress(min(q_rate / 100, 1.0))
        if q_rate >= 80: st.success("🌟 素晴らしい！授業の定着度を毎回しっかり計測できています！")
        elif q_rate >= 50: st.info("👍 半数以上の授業でテストを実施できています。")
        else: st.warning("⚠️ 実施率が低めです。授業の冒頭で小テストを行い、結果を記録するルーティンを徹底しましょう。")

        st.divider()
        st.markdown(f"**💬 保護者ファン化度・エンゲージメント詳細**")
        
        reply_counts = df_t['保護者リアクション'].value_counts()
        
        col_r1, col_r2 = st.columns([4, 6])
        with col_r1:
            st.write("📊 **リアクション内訳**")
            for k, v in reply_counts.items():
                st.write(f"- {k}: **{v}** 件")
        with col_r2:
            # 🌟 修正：ここも既読スルーを除外したデータが空でない場合のみグラフを描画
            df_t_react_only = df_t[df_t['保護者リアクション'] != "🔵 既読スルー（自動カウント）"]
            if not df_t_react_only.empty:
                df_t_pivot = pd.crosstab(df_t_react_only['担当講師'], df_t_react_only['保護者リアクション'])
                st.bar_chart(df_t_pivot, stack=True)
            else:
                st.info("今月はまだ保護者からのポジティブリアクションはありません。")
            
        if star_rate >= 30:
            st.success(f"🔥 **超優秀ファンタジスタ講師！** 報告書の3割以上で保護者から大絶賛（神対応）を貰っています。保護者からの信頼が極めて厚いため、今後の提案業務などの中心人物として活躍が期待できます。")
        elif star_rate > 0 or reply_counts.get("🟢 好意的・納得（信頼構築・塾への指示通りに家庭が動く状態）", 0) > 0:
            st.info(f"👍 **良好な信頼関係です。** 既読スルーの山の中に、しっかりと保護者からの感謝や納得のサインが隠れています。引き続き丁寧な報告を継続しましょう。")
        else:
            st.warning(f"⚠️ **要注意サイン:** 今月は保護者から自発的なポジティブリアクションが1件もありません（すべて自動の既読スルー扱いです）。報告書の文章が事務的になっていないか、一度内容をチェックしてみましょう。")