import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
import time 

from utils.g_sheets import load_self_study_data, get_all_logs, get_student_master
from utils.api_guard import robust_api_call

def render_self_study_dashboard():
    # --- 🖨️ 印刷用の魔法（横向き・横幅最大化・ページまたぎ許可版） ---
    st.markdown("""
        <style>
        @media print {
            /* 1. 用紙の強制設定 */
            @page {
                size: landscape; 
                margin: 5mm 10mm; /* 上下左右の余白を少しだけ確保 */
            }

            /* 🌟 2. Streamlitの大元の箱の「幅制限」を完全に破壊する */
            html, body, [data-testid="stApp"], .main, .block-container, 
            [data-testid="stAppViewContainer"], 
            [data-testid="stAppViewBlockContainer"],
            [data-testid="stVerticalBlock"],
            [data-testid="stVerticalBlockBorderWrapper"],
            [data-testid="element-container"],
            [data-testid="stTabs"],        
            [role="tabpanel"] {            
                display: block !important;
                width: 100% !important;
                max-width: 100% !important; /* 💥 ここが一番重要：最大幅の制限を解除！ */
                padding: 0 !important;
                margin: 0 !important;
            }

            /* 不要なものをすべて非表示（👆アイコン含む） */
            header, footer, [data-testid="stHeader"], [data-testid="stSidebar"], 
            [data-testid="stForm"], .stButton, [data-testid="stCaptionContainer"],
            [data-testid="stTable"], .print-table-title,
            [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] h1, 
            [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3, 
            [data-testid="stHeadingWithActionElements"], iframe, .stProgress,
            #vg-tooltip-element, .vg-tooltip, 
            [data-testid="stAlert"], [data-baseweb="notification"], div[role="alert"] { 
                display: none !important; 
            }

            /* 🌟 3. タイトルを一番上に配置 */
            .print-title { 
                display: block !important; 
                text-align: center !important; 
                font-size: 24px !important; 
                font-weight: bold !important; 
                margin: -90px auto 0 auto !important; 
                padding: 0 !important;
                page-break-after: avoid !important;
                break-after: avoid !important;
            }

            /* 🌟 4. グラフの幅を100%に広げ、高さは自動で伸ばす */
            [data-testid="stArrowVegaLiteChart"],
            .vega-embed {
                display: block !important;
                width: 100% !important;
                max-width: 100% !important;
                height: auto !important; /* 縦はPython側で計算した高さまで自由に伸ばす */
                margin: -60px 0 0 0 !important;
                padding: 0 !important;
                page-break-inside: auto !important;
                break-inside: auto !important;
            }
            
            /* 🌟 5. グラフ画像自体を枠いっぱいに広げる */
            [data-testid="stArrowVegaLiteChart"] canvas,
            [data-testid="stArrowVegaLiteChart"] svg,
            .vega-embed canvas,
            .vega-embed svg {
                width: 100% !important;       
                max-width: 100% !important;   
                height: auto !important;      
                object-fit: contain !important; /* 画像の比率を保ったまま広げる */
                display: block !important;
                margin: 0 !important;
            }
            
            /* タブの横にあるスクロール用矢印を消す */
            [data-testid="stTabs"] button {
                display: none !important;
            }

            /* 背景色・文字色の調整 */
            * {
                background-color: transparent !important;
                color: black !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
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
                st.cache_data.clear() # 🌟 変更: アプリ全体のキャッシュをクリアしてリロード
                st.rerun() 
                
        with btn_col2:
            # 🌟 【修正箇所】枠線が切れないように高さを広げ、見えない余白をリセット！
            components.html(
                """
                <style>
                    /* ブラウザ特有の余計な余白を消して、ボタンの周りに少しだけ安全な隙間を作る */
                    body { margin: 0; padding: 2px; box-sizing: border-box; }
                </style>
                <div style="display: flex; justify-content: center; align-items: center; height: 100%;">
                    <button onclick="window.parent.print()" style="
                        background-color: white;
                        border: 1px solid #dcdcdc;
                        color: #31333F;
                        padding: 0.35rem 0.75rem;
                        font-size: 16px;
                        border-radius: 8px;
                        cursor: pointer;
                        width: 100%;
                        font-family: sans-serif;
                        box-shadow: 0px 1px 2px rgba(0,0,0,0.05);
                        transition: all 0.2s ease;
                    " onmouseover="this.style.borderColor='#ff4b4b'; this.style.color='#ff4b4b';" 
                      onmouseout="this.style.borderColor='#dcdcdc'; this.style.color='#31333F';">
                        🖨️ グラフを印刷
                    </button>
                </div>
                """,
                height=55 # 💥 枠の高さを「45」から「55」に広げて、下切れを防止！
            )
            
        st.caption("※スマホはブラウザの「共有」メニューからプリントしてください")
    
    st.write("自習時間と授業時間を合算したり、学年ごとに絞り込んだりできる究極のグラフです🔥")
    # ==========================================
    # 1. UI（コントローラー）の作成 
    # ==========================================
    # 🌟 データを読み込む前に月を選べるよう、過去12ヶ月のリストを自動作成
    today = pd.Timestamp.today()
    month_list = [(today - pd.DateOffset(months=i)).strftime('%Y年%m月') for i in range(12)]
    
    # 🌟 変更: 学年データを get_student_master から取得！
    df_grades = robust_api_call(get_student_master, fallback_value=pd.DataFrame())

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
        progress_bar.progress(20, text="☁️ 自習データを取得中...")
        
        # 🛡️ ガード適用 1: 自習データの取得
        df_self_study = robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())
        
        # エラー専用のDataFrameじゃないことを確認してから処理
        if not df_self_study.empty and 'APIエラー発生' not in df_self_study.columns:
            df_self_study['日付'] = pd.to_datetime(df_self_study['日付'], errors='coerce')
            df_self_study = df_self_study.dropna(subset=['日付'])
            df_self_study['年月'] = df_self_study['日付'].dt.strftime('%Y年%m月')
            df_self_study['自習時間(分)'] = pd.to_numeric(df_self_study['自習時間(分)'], errors='coerce').fillna(0)
        else:
            df_self_study = pd.DataFrame() # エラー時は安全のため空にしておく
        
        # プログレスバー更新：60%
        progress_bar.progress(60, text="☁️ 授業データを取得中...")
        
        # 🌟 変更: load_entire_log_data ではなく get_all_logs を使用！
        df_classes = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())
        
        # エラー専用のDataFrameじゃないことを確認してから処理
        if not df_classes.empty and 'APIエラー発生' not in df_classes.columns:
            # 🛡️ 【究極の防衛策 1】インデックス（行番号）が悪さをしないようにリセット
            df_classes = df_classes.reset_index(drop=True)
            
            # 🛡️ 【究極の防衛策 2】列名の前後に隠れている「見えない空白」をすべて抹殺
            df_classes.columns = [str(c).strip() for c in df_classes.columns]
            
            # 🛡️ 【究極の防衛策 3】完全な重複列をここで物理的に排除
            df_classes = df_classes.loc[:, ~df_classes.columns.duplicated()]
            
            # --- 列名の統一処理 ---
            if '名前' in df_classes.columns:
                if '生徒名' in df_classes.columns:
                    # 「名前」と「生徒名」両方ある場合は、「名前」列の方を削除して統一
                    df_classes = df_classes.drop(columns=['名前'])
                else:
                    # 「生徒名」がない場合は、「名前」を「生徒名」にリネーム
                    df_classes = df_classes.rename(columns={'名前': '生徒名'})
            
            # 🛡️ 【究極の防衛策 4】万が一「生徒名」が複数列（2D）の塊になっていたら、最初の1列だけを引っこ抜く
            if '生徒名' in df_classes.columns and isinstance(df_classes['生徒名'], pd.DataFrame):
                clean_series = df_classes['生徒名'].iloc[:, 0].copy() # 1列目だけ確保
                df_classes = df_classes.drop(columns=['生徒名'])      # 一旦全部消す
                df_classes['生徒名'] = clean_series                    # 綺麗な1列だけ戻す

            # --- 日付の処理 ---
            date_col = '日時' if '日時' in df_classes.columns else ('日付' if '日付' in df_classes.columns else None)
            
            if date_col:
                df_classes[date_col] = pd.to_datetime(df_classes[date_col], errors='coerce')
                df_classes = df_classes.dropna(subset=[date_col])
                df_classes['年月'] = df_classes[date_col].dt.strftime('%Y年%m月')
        else:
            df_classes = pd.DataFrame() # エラー時は安全のため空にしておく

        progress_bar.progress(90, text="⚙️ データを合算・計算中...")

    # --- 以下、3. データの絞り込みと合算 へ続く ---
    if df_self_study.empty and df_classes.empty:
        progress_bar.empty()
        st.info("学習記録がまだありません、または通信エラーによりデータを取得できませんでした。")
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

    # 💡 df_classes に「生徒名」が含まれているかもチェック条件に追加
    if mode == "自習時間 ＋ 授業時間" and not df_classes.empty and '生徒名' in df_classes.columns:
        df_cl_filtered = df_classes.copy()
        if selected_month != "すべての期間（累計）":
            df_cl_filtered = df_cl_filtered[df_cl_filtered['年月'] == selected_month]
        
        # 💡 【改善3】欠席したコマを計算から除外！（出欠列に「出席」という文字が含まれるものだけ残す）
        if '出欠' in df_cl_filtered.columns:
            df_cl_filtered = df_cl_filtered[df_cl_filtered['出欠'].astype(str).str.contains('出席', na=False)]
        
        cl_grouped = df_cl_filtered.groupby('生徒名').size().reset_index(name='コマ数')
        cl_grouped['授業時間(分)'] = cl_grouped['コマ数'] * 90
        
        merged = pd.merge(ss_grouped, cl_grouped[['生徒名', '授業時間(分)']], on='生徒名', how='outer').fillna(0)
        merged['合計時間(分)'] = merged['自習時間(分)'] + merged['授業時間(分)']
    else:
        merged = ss_grouped.copy()
        if '自習時間(分)' not in merged.columns:
            merged['自習時間(分)'] = 0
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

    # --- 🌟 人数に応じたサイズ自動調整機能 ---
    num_students = len(merged)
    
    if num_students <= 5:
        multiplier = 50    # 5人以下：かなり広く（1人50px）
        bar_size = 30      # 棒を極太に
    elif num_students <= 10:
        multiplier = 40    # 6〜10人：広めに（1人40px）
        bar_size = 22      # 棒を太めに
    elif num_students <= 30:
        multiplier = 25    # 11〜30人：標準（1人25px）
        bar_size = 15      # 棒を標準サイズに
    else:
        multiplier = 13    # 31人以上：詰め気味（1人13px）
        bar_size = 10      # 棒を細めに

    # 全体の高さを計算（最低300pxは確保）
    chart_height = max(300, num_students * multiplier)
    # ---------------------------------------

    grade_display = " / ".join(selected_grades) if len(selected_grades) <= 4 else "全学年"
    title_html = f"""
    <div class='print-title'>
        🏆 勉強時間ランキング ({grade_display}) - {selected_month}
    </div>
    """
    st.markdown(title_html, unsafe_allow_html=True)

    merged = merged.sort_values(by='合計時間(分)', ascending=False)
    sorted_students = merged['生徒名'].tolist() 

    # 軸の設定（labelOverlap=False で名前の省略を絶対禁止）
    y_encoding = alt.Y('生徒名:N', sort=sorted_students, title=None, axis=alt.Axis(labelFontSize=12, labelOverlap=False))

    if mode == "自習時間 ＋ 授業時間":
        plot_df = pd.melt(merged, id_vars=['生徒名', '合計時間(分)'], value_vars=['自習時間(分)', '授業時間(分)'], var_name='時間の種類', value_name='時間')
        
        # size=bar_size を適用
        bars = alt.Chart(plot_df).mark_bar(cornerRadiusEnd=4, size=bar_size).encode(
            x=alt.X('時間:Q', title='学習時間 (分)'),
            y=y_encoding,
            color=alt.Color('時間の種類:N', scale=alt.Scale(domain=['自習時間(分)', '授業時間(分)'], range=['#ff7f0e', '#1f77b4']), legend=alt.Legend(title=None, orient="top", offset=-5, labelFontSize=10)),
            tooltip=['生徒名', '時間の種類', '時間', '合計時間(分)']
        )
        
        text = alt.Chart(merged).mark_text(align='left', baseline='middle', dx=5, fontSize=12, fontWeight='bold', color='#333').encode(
            x='合計時間(分):Q',
            y=y_encoding,
            text=alt.Text('合計時間(分):Q', format='d')
        )
        
        chart = alt.layer(bars, text).properties(height=chart_height)
        
    else:
        # size=bar_size を適用
        bars = alt.Chart(merged).mark_bar(cornerRadiusEnd=4, size=bar_size).encode(
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
    # 🌟 印刷時にも消えない専用の見出しに変更
    st.markdown("<div class='print-table-title'>📋 詳細データ</div>", unsafe_allow_html=True)
    
    display_df = merged.sort_values(by='合計時間(分)', ascending=False).reset_index(drop=True)
    display_df.index = display_df.index + 1
    
    if mode == "自習時間 ＋ 授業時間":
        cols_to_show = ['生徒名', '学年', '合計時間(分)', '自習時間(分)', '授業時間(分)']
    else:
        cols_to_show = ['生徒名', '学年', '自習時間(分)']
        
    # 🌟 印刷で途切れないように st.dataframe から st.table に変更！
    st.table(display_df[cols_to_show])