import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
import time

# ==========================================
# 🛡️ APIエラー対策：データ読み込み関数群（追加・更新）
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def cached_load_self_study_by_student(student_name):
    """特定の生徒の自習データを取得して月別に集計する"""
    from utils.g_sheets import load_self_study_data
    max_retries = 5
    df = pd.DataFrame()
    
    for attempt in range(max_retries):
        try:
            df = load_self_study_data()
            break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return pd.DataFrame()

    if df.empty or '生徒名' not in df.columns:
        return pd.DataFrame()
    
    # 該当生徒のみ抽出
    df_student = df[df['生徒名'] == student_name].copy()
    if df_student.empty:
        return pd.DataFrame()
        
    # 日付と時間を数値化
    df_student['日付'] = pd.to_datetime(df_student['日付'], errors='coerce')
    df_student = df_student.dropna(subset=['日付'])
    df_student['年月'] = df_student['日付'].dt.strftime('%Y年%m月')
    df_student['自習時間(分)'] = pd.to_numeric(df_student['自習時間(分)'], errors='coerce').fillna(0)
    
    # 月ごとに合計を計算
    df_monthly = df_student.groupby('年月')['自習時間(分)'].sum().reset_index()
    
    # 月順に正しく並べるためのソート用キー
    df_monthly['sort_key'] = pd.to_datetime(df_monthly['年月'], format='%Y年%m月')
    df_monthly = df_monthly.sort_values('sort_key').drop(columns=['sort_key'])
    
    return df_monthly

# (他の既存のcached関数はそのまま...)
@st.cache_data(ttl=600, show_spinner=False)
def safe_load_test_scores():
    from utils.g_sheets import load_test_scores
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return load_test_scores()
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def cached_get_textbook_master():
    from utils.g_sheets import get_textbook_master
    return get_textbook_master()

@st.cache_data(ttl=600, show_spinner=False)
def cached_load_quiz_data(student_name):
    from utils.g_sheets import load_quiz_data_from_dedicated_sheet
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return load_quiz_data_from_dedicated_sheet(student_name)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def cached_calculate_attendance_rate(student_name):
    from utils.g_sheets import load_raw_data
    max_retries = 5
    df_attendance = pd.DataFrame()
    for attempt in range(max_retries):
        try:
            df_attendance = load_raw_data(student_name)
            break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return "取得エラー"
    if df_attendance.empty or '出欠' not in df_attendance.columns:
        return "データなし"
    attend_keywords = ['出席（通常）', '出席（振替授業を消化）']
    absent_keywords = ['欠席（後日振替あり）', '欠席（振替なし）']
    records = df_attendance['出欠'].dropna().astype(str)
    attend_count = records.isin(attend_keywords).sum()
    absent_count = records.isin(absent_keywords).sum()
    total_lessons = attend_count + absent_count
    if total_lessons == 0: return "0% (履歴なし)"
    rate = (attend_count / total_lessons) * 100
    return f"{int(rate)}%"

# ==========================================
# 🎯 面談レポート画面のメイン関数
# ==========================================
def render_conference_report(selected_student, info):
    # --- 🖨️ 印刷用の魔法（既存のまま） ---
    st.markdown("""
        <style>
        @media print {
            [data-testid="stAlert"], header, [data-testid="stHeader"], [data-testid="stSidebar"], footer { display: none !important; }
            .stButton, [data-testid="stRadio"], [data-testid="stSpinner"] { display: none !important; }
            * { background-color: transparent !important; }
            .main .block-container { padding-top: 0 !important; margin-top: 0 !important; gap: 10px !important; max-width: 100% !important; }
            [data-testid="stTable"], [data-testid="stDataFrame"], [data-testid="stArrowVegaLiteChart"], [data-testid="stMetric"] { 
                page-break-inside: avoid !important; 
            }
        }
        </style>
    """, unsafe_allow_html=True)

    col_title, col_print = st.columns([4, 1])
    with col_title:
        st.header(f"🎓 {selected_student} さん 面談レポート")
    with col_print:
        if st.button("🖨️ レポートを印刷"):
            components.html("<script>window.parent.print();</script>", height=0)

    st.caption("※データ読み込み専用画面です。通信エラーを防ぐため一時保存データを表示しています。")

    with st.spinner("学習データを集計中..."):
        master_dict = cached_get_textbook_master()
        df_quiz = cached_load_quiz_data(selected_student)
        df_test_all = safe_load_test_scores()
        # 💡 追加：自習データの読み込み
        df_monthly_ss = cached_load_self_study_by_student(selected_student)

    # 既存のテストデータ抽出
    df_student_tests = pd.DataFrame()
    if not df_test_all.empty:
        df_student_tests = df_test_all[df_test_all['生徒名'] == selected_student]

    st.divider()

    # ==========================================
    # 1. 宿題・出席・努力の量
    # ==========================================
    st.subheader("🔥 学習への取り組み姿勢")
    col1, col2, col3, col4 = st.columns(4)
    
    with st.spinner("出席率を計算中..."):
        attendance_rate = cached_calculate_attendance_rate(selected_student)
    
    hw_rate_str = str(info.get('宿題履行率', '0')).replace('%', '')
    try:
        hw_rate = float(hw_rate_str)
    except ValueError:
        hw_rate = 0.0

    col1.metric("🏠 宿題履行率", f"{hw_rate}%")
    col2.metric("📅 出席率", attendance_rate)
    
    total_quiz_attempts = len(df_quiz) if not df_quiz.empty else 0
    col3.metric("📝 小テスト総回数", f"{total_quiz_attempts} 回")
    col4.metric("🎯 志望校・目標", info.get('志望校・目的', '未設定'))

    # 💡 追加：自習時間の月別グラフを表示
    st.write("#### 📅 月別の自習時間（努力の可視化）")
    if not df_monthly_ss.empty:
        # 横軸が時間、縦軸が月のバーチャート
        ss_chart = alt.Chart(df_monthly_ss).mark_bar(
            cornerRadiusEnd=4, 
            color='#ff7f0e', # 教室カラーなどに合わせて調整してください
            size=20
        ).encode(
            x=alt.X('自習時間(分):Q', title='合計自習時間 (分)'),
            y=alt.Y('年月:N', title='月', sort=None), # ソートはデータフレーム側で済ませているのでNone
            tooltip=['年月', '自習時間(分)']
        ).properties(height=200)

        # 棒の横に数値を表示
        ss_text = ss_chart.mark_text(
            align='left',
            baseline='middle',
            dx=5,
            fontWeight='bold'
        ).encode(
            text=alt.Text('自習時間(分):Q', format='d')
        )

        st.altair_chart(ss_chart + ss_text, use_container_width=True)
    else:
        st.info("自習記録がまだありません。これからの頑張りを記録していきましょう！")

    if hw_rate >= 90: st.success("素晴らしい取り組みです！この学習習慣が成績向上の最大の武器になります。")
    elif hw_rate >= 70: st.info("概ね良好に学習できています。間違えた問題の解き直しを徹底するとさらに伸びます。")
    else: st.warning("まずは宿題をやり切る習慣づけが必要です。ご家庭での学習時間の固定化をご協力お願いします。")

    st.divider()

    # ==========================================
    # 2. 学校成績の推移（既存のまま）
    # ==========================================
    # ... (中略：既存の成績グラフコード) ...
    st.subheader("📈 成績の推移")
    if not df_student_tests.empty:
        view_type = st.radio("表示データ：", ["定期テスト", "模試", "内申（通知表）"], horizontal=True, key="view_type_radio")
        date_col = '実施日' if '実施日' in df_student_tests.columns else '日付' if '日付' in df_student_tests.columns else '日時' if '日時' in df_student_tests.columns else None
        type_col = 'テスト種別' if 'テスト種別' in df_student_tests.columns else 'テスト名' if 'テスト名' in df_student_tests.columns else None
        if date_col:
            if view_type == "定期テスト":
                df_plot = df_student_tests[df_student_tests[type_col].astype(str).str.contains("テスト|期末|中間|実力", na=False)].copy()
                subjects, y_label, y_domain = ["英語", "数学", "国語", "理科", "社会"], "点数", [0, 100]
            elif view_type == "模試":
                df_plot = df_student_tests[df_student_tests[type_col].astype(str).str.contains("模試|下野|もぎ", na=False)].copy()
                subjects, y_label, y_domain = ["英語", "数学", "国語", "理科", "社会"], "偏差値", [0, 100]
            else:
                df_plot = df_student_tests.copy()
                subjects, y_label, y_domain = ["英語 内申", "数学 内申", "国語 内申", "理科 内申", "社会 内申"], "評定", [1, 5]

            if not df_plot.empty:
                df_plot[date_col] = pd.to_datetime(df_plot[date_col], errors='coerce')
                df_plot = df_plot.sort_values(date_col)
                available_subjects = [s for s in subjects if s in df_plot.columns]
                if available_subjects:
                    df_melted = df_plot.melt(id_vars=[date_col], value_vars=available_subjects, var_name='科目', value_name='スコア')
                    df_melted['スコア'] = pd.to_numeric(df_melted['スコア'], errors='coerce').dropna()
                    chart = alt.Chart(df_melted).mark_line(point=True).encode(
                        x=alt.X(f'{date_col}:T', title='実施日'),
                        y=alt.Y('スコア:Q', scale=alt.Scale(domain=y_domain), title=y_label),
                        color=alt.Color('科目:N'),
                        tooltip=[date_col, '科目', 'スコア']
                    ).properties(height=350)
                    st.altair_chart(chart, use_container_width=True)
    
    st.divider()

    # ==========================================
    # 3. 小テスト進捗の一覧（テキスト別サマリー）
    # ==========================================
    st.subheader("📊 小テスト（基礎学力）の定着状況")
    if master_dict and not df_quiz.empty:
        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        summary_data = []
        
        attempted_texts = df_quiz['テキスト'].dropna().unique()
        
        for text_name in attempted_texts:
            if text_name not in master_dict:
                continue
                
            chaps = master_dict[text_name]
            total_chaps = len(chaps)
            df_text = df_quiz[(df_quiz['テキスト'] == text_name) & (df_quiz['点数'] >= 80)]
            done_chaps = df_text['単元'].nunique() if '単元' in df_text.columns else 0
            
            progress = int((done_chaps / total_chaps) * 100) if total_chaps > 0 else 0
            summary_data.append({
                "テキスト名": text_name,
                "進捗率(%)": progress,
                "合格章数": f"{done_chaps} / {total_chaps} 章"
            })
            
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            bar_chart = alt.Chart(df_summary).mark_bar().encode(
                x=alt.X('進捗率(%):Q', scale=alt.Scale(domain=[0, 100])),
                y=alt.Y('テキスト名:N', sort='-x'),
                color=alt.Color('進捗率(%):Q', scale=alt.Scale(scheme='blues')),
                tooltip=['テキスト名', '進捗率(%)', '合格章数']
            ).properties(height=200)
            st.altair_chart(bar_chart, use_container_width=True)
            
            st.table(df_summary.set_index("テキスト名"))
        else:
            st.info("集計できる小テストデータがありません。")
    else:
        st.info("小テストのデータがまだありません。")

    # ==========================================
    # 4. 弱点分析（おすすめデータ：今後の対策）
    # ==========================================
    st.subheader("💡 優先して復習すべき単元（自動ピックアップ）")
    if not df_quiz.empty:
        df_weak = df_quiz[df_quiz['点数'] < 60].sort_values(by='日時', ascending=False).head(5)
        if not df_weak.empty:
            st.write("以下の単元は、直近のテストで点数が伸び悩んだため、次回の授業や講習で優先的に対策を行います。")
            display_weak = df_weak[['日時', 'テキスト', '単元', '点数', 'ミス番号']]
            
            st.table(display_weak.set_index("日時"))
        else:
            st.success("現在、極端に点数が低い（苦手な）単元は見当たりません！順調です。")