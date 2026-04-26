import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
import time 
import gspread 
from utils.g_sheets import load_self_study_data, load_entire_log_data, get_gc_client, SPREADSHEET_ID

@st.cache_data(ttl=600)
def get_all_student_grades():
    """生徒情報から学年データを取得する魔法（APIエラー対策版）"""
    gc = get_gc_client()
    max_retries = 7

    for attempt in range(max_retries):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("設定_生徒情報")
            df = pd.DataFrame(ws.get_all_records())
            
            # 無事にデータが取れたら返す
            if not df.empty:
                return df
                
        except gspread.exceptions.APIError:
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except Exception:
            time.sleep(2)
            
    # キャッシュを破棄して空のDataFrameを返す
    get_all_student_grades.clear()
    return pd.DataFrame()

def render_self_study_dashboard():
    # --- 🖨️ 印刷用の魔法 ---
    st.markdown("""
        <style>
        @media print {
            [data-testid="stAlert"] { display: none !important; }
            * { background-color: transparent !important; }
            .main .block-container { padding-top: 0 !important; margin-top: 0 !important; gap: 0 !important; max-width: 100% !important; }
            header, [data-testid="stHeader"], [data-testid="stSidebar"], footer { display: none !important; }
            .stButton, [data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stRadio"], [data-testid="stDataFrame"], [data-testid="stSpinner"], hr { display: none !important; }
            h1, h2, h3, h4, h5, h6, p, [data-testid="stMarkdownContainer"] p { display: none !important; margin: 0 !important; padding: 0 !important; }
            .print-title { display: block !important; text-align: center !important; color: black !important; font-size: 26px !important; font-weight: bold !important; margin-top: 0px !important; margin-bottom: 10px !important; padding: 0 !important; }
            [data-testid="stArrowVegaLiteChart"] { display: block !important; width: 100% !important; margin: 0 auto !important; padding: 0 !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("📊 学習時間ダッシュボード")
    with col2:
        # 🌟 リロードボタンを追加！
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🔄 最新データに更新"):
                get_all_student_grades.clear() # キャッシュを消去
                st.rerun() # 画面をリロード
        with btn_col2:
            if st.button("🖨️ グラフを印刷"):
                components.html("<script>window.parent.print();</script>", height=0)
        st.caption("※スマホはブラウザの「共有」メニューからプリントしてください")
    
    st.write("自習時間と授業時間を合算したり、学年ごとに絞り込んだりできる究極のグラフです🔥")

    # ==========================================
    # 1. UI（コントローラー）の作成 
    # ==========================================
    # 🌟 データを読み込む前に月を選べるよう、過去12ヶ月のリストを自動作成
    today = pd.Timestamp.today()
    month_list = [(today - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(12)]
    
    # 学年データは軽いので先に取得
    df_grades = get_all_student_grades()

    # 🌟 フォームを追加して、ボタンを押すまで読み込まないようにする
    with st.form("self_study_filter_form"):
        st.markdown("### 🎛️ 表示設定")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            selected_month = st.selectbox("📅 月を選択", ["すべての期間（累計）"] + month_list)
        
        with c2:
            mode = st.radio("⏱️ 表示モード", ["自習時間のみ", "自習時間 ＋ 授業時間"])
            
        with c3:
            valid_grades = []
            if not df_grades.empty and '学年' in df_grades.columns:
                valid_grades = sorted([g for g in df_grades['学年'].unique() if str(g).strip() != ""])
            
            if not valid_grades:
                st.warning("⚠️ 学年データの取得に一時的に失敗しました。リロードしてください。")
                st.form_submit_button("ダミーボタン") # フォームエラー回避用
                st.stop()
                
            selected_grades = st.multiselect("🎓 学年で絞り込み (複数選択可)", options=valid_grades, default=valid_grades)

        submit_btn = st.form_submit_button("🚀 この条件で集計を開始する")

    # 🌟 ボタンが押されていなければここでストップ
    if not submit_btn:
        st.info("👆 上のメニューから条件を選んで、「集計を開始する」ボタンを押してください。")
        return

    # ==========================================
    # 2. データの読み込み (プログレスバー付き！)
    # ==========================================
    progress_bar = st.progress(0, text="🚀 データの集計を準備中...")
    
    with st.spinner("あらゆる学習データをかき集めています..."):
        # プログレスバー更新：20%
        progress_bar.progress(20, text="☁️ 自習データを取得中...")
        df_self_study = load_self_study_data()
        if not df_self_study.empty:
            df_self_study['日付'] = pd.to_datetime(df_self_study['日付'], errors='coerce')
            df_self_study = df_self_study.dropna(subset=['日付'])
            df_self_study['年月'] = df_self_study['日付'].dt.strftime('%Y年%m月')
            df_self_study['自習時間(分)'] = pd.to_numeric(df_self_study['自習時間(分)'], errors='coerce').fillna(0)
        
        # プログレスバー更新：60%
        progress_bar.progress(60, text="☁️ 授業データを取得中...")
        df_classes = load_entire_log_data()
        if not df_classes.empty and '日時' in df_classes.columns:
            df_classes['日時'] = pd.to_datetime(df_classes['日時'], format='mixed', errors='coerce')
            df_classes = df_classes.dropna(subset=['日時'])
            df_classes['年月'] = df_classes['日時'].dt.strftime('%Y年%m月')

        # プログレスバー更新：90%
        progress_bar.progress(90, text="⚙️ データを合算・計算中...")

    if df_self_study.empty and df_classes.empty:
        progress_bar.empty()
        st.info("学習記録がまだありません。")
        return

    # ==========================================
    # 3. データの絞り込みと合算
    # ==========================================
    if not df_self_study.empty:
        df_ss_filtered = df_self_study.copy()
        if selected_month != "すべての期間（累計）":
            df_ss_filtered = df_ss_filtered[df_ss_filtered['年月'] == selected_month]
        ss_grouped = df_ss_filtered.groupby('生徒名')['自習時間(分)'].sum().reset_index()
    else:
        ss_grouped = pd.DataFrame(columns=['生徒名', '自習時間(分)'])

    if mode == "自習時間 ＋ 授業時間" and not df_classes.empty:
        df_cl_filtered = df_classes.copy()
        if selected_month != "すべての期間（累計）":
            df_cl_filtered = df_cl_filtered[df_cl_filtered['年月'] == selected_month]
        
        cl_grouped = df_cl_filtered.groupby('生徒名').size().reset_index(name='コマ数')
        cl_grouped['授業時間(分)'] = cl_grouped['コマ数'] * 90
        
        merged = pd.merge(ss_grouped, cl_grouped[['生徒名', '授業時間(分)']], on='生徒名', how='outer').fillna(0)
        merged['合計時間(分)'] = merged['自習時間(分)'] + merged['授業時間(分)']
    else:
        merged = ss_grouped.copy()
        merged['授業時間(分)'] = 0
        merged['合計時間(分)'] = merged['自習時間(分)']

    if not df_grades.empty and '生徒名' in df_grades.columns and '学年' in df_grades.columns:
        merged = pd.merge(merged, df_grades[['生徒名', '学年']], on='生徒名', how='left')
        merged['学年'] = merged['学年'].fillna('不明')
    else:
        merged['学年'] = '不明'

    if selected_grades:
        merged = merged[merged['学年'].isin(selected_grades)]
    else:
        progress_bar.empty()
        st.warning("学年が1つも選択されていません。表示したい学年を選んでください！")
        return

    # プログレスバー更新：100%（完了したら消す）
    progress_bar.progress(100, text="✨ 集計完了！グラフを描画します")
    time.sleep(0.5)
    progress_bar.empty()

    # ==========================================
    # 4. グラフの描画
    # ==========================================
    if merged.empty or merged['合計時間(分)'].sum() == 0:
        st.info("指定された条件のデータがありませんでした。")
        return

    grade_display = " / ".join(selected_grades) if len(selected_grades) <= 4 else "全学年"
    title_html = f"""
    <div class='print-title'>
        🏆 勉強時間ランキング ({grade_display}) - {selected_month}
    </div>
    """
    st.markdown(title_html, unsafe_allow_html=True)

    merged = merged.sort_values(by='合計時間(分)', ascending=False)
    sorted_students = merged['生徒名'].tolist() 

    chart_height = max(300, len(merged) * 30)
    y_encoding = alt.Y('生徒名:N', sort=sorted_students, title='生徒名', axis=alt.Axis(labelFontSize=12))

    if mode == "自習時間 ＋ 授業時間":
        plot_df = pd.melt(merged, id_vars=['生徒名', '合計時間(分)'], value_vars=['自習時間(分)', '授業時間(分)'], var_name='時間の種類', value_name='時間')
        
        bars = alt.Chart(plot_df).mark_bar(cornerRadiusEnd=4, size=14).encode(
            x=alt.X('時間:Q', title='学習時間 (分)'),
            y=y_encoding,
            color=alt.Color('時間の種類:N', scale=alt.Scale(domain=['自習時間(分)', '授業時間(分)'], range=['#ff7f0e', '#1f77b4']), legend=alt.Legend(title="学習の種類", orient="top")),
            tooltip=['生徒名', '時間の種類', '時間', '合計時間(分)']
        )
        
        text = alt.Chart(merged).mark_text(align='left', baseline='middle', dx=5, fontSize=12, fontWeight='bold', color='#333').encode(
            x='合計時間(分):Q',
            y=y_encoding,
            text=alt.Text('合計時間(分):Q', format='d')
        )
        
        chart = alt.layer(bars, text).properties(height=chart_height)
        
    else:
        bars = alt.Chart(merged).mark_bar(cornerRadiusEnd=4, size=14).encode(
            x=alt.X('合計時間(分):Q', title='自習時間 (分)'),
            y=y_encoding,
            color=alt.Color('合計時間(分):Q', scale=alt.Scale(scheme='blues'), legend=None),
            tooltip=['生徒名', '合計時間(分)']
        )
        
        text = alt.Chart(merged).mark_text(align='left', baseline='middle', dx=5, fontSize=12, fontWeight='bold', color='#333').encode(
            x='合計時間(分):Q',
            y=y_encoding,
            text=alt.Text('合計時間(分):Q', format='d')
        )
        
        chart = alt.layer(bars, text).properties(height=chart_height)

    st.altair_chart(chart, use_container_width=True)

    # ==========================================
    # 5. 詳細データ表の表示
    # ==========================================
    st.markdown("### 📋 詳細データ")
    display_df = merged.sort_values(by='合計時間(分)', ascending=False).reset_index(drop=True)
    display_df.index = display_df.index + 1
    
    if mode == "自習時間 ＋ 授業時間":
        cols_to_show = ['生徒名', '学年', '合計時間(分)', '自習時間(分)', '授業時間(分)']
    else:
        cols_to_show = ['生徒名', '学年', '自習時間(分)']
        
    st.dataframe(display_df[cols_to_show], use_container_width=True)