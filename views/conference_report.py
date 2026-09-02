import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components
import io  # 🌟 NEW: Excelファイルをメモリ上で作るための部品
import re  # 🌟 NEW: ファイル名を安全にするための部品

# 🌟 APIガードをインポート
from utils.api_guard import robust_api_call
# 🌟 計算専門の関数をインポート！
from utils.calc_logic import calculate_score_ratio

# ==========================================
# 🛡️ APIエラー対策：データ読み込み関数群
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def cached_load_self_study_by_student(student_name):
    from utils.g_sheets import load_self_study_data
    df = robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())

    if df.empty or '名前' not in df.columns or "APIエラー発生" in df.columns:
        return pd.DataFrame()
    
    df_student = df[df['名前'] == student_name].copy()
    if df_student.empty:
        return pd.DataFrame()
        
    df_student['日付'] = pd.to_datetime(df_student['日付'], errors='coerce')
    df_student = df_student.dropna(subset=['日付'])
    df_student['年月'] = df_student['日付'].dt.strftime('%Y年%m月')
    df_student['自習時間(分)'] = pd.to_numeric(df_student['自習時間(分)'], errors='coerce').fillna(0)
    
    df_monthly = df_student.groupby('年月')['自習時間(分)'].sum().reset_index()
    df_monthly['sort_key'] = pd.to_datetime(df_monthly['年月'], format='%Y年%m月')
    df_monthly = df_monthly.sort_values('sort_key').drop(columns=['sort_key'])
    
    return df_monthly

@st.cache_data(ttl=600, show_spinner=False)
def safe_load_test_scores():
    from utils.g_sheets import load_test_scores
    return robust_api_call(load_test_scores, fallback_value=pd.DataFrame())

def cached_get_textbook_master():
    from utils.g_sheets import get_textbook_master
    return robust_api_call(get_textbook_master, fallback_value={})

@st.cache_data(ttl=600, show_spinner=False)
def cached_load_quiz_data(student_name):
    from utils.g_sheets import load_quiz_data_from_dedicated_sheet
    return robust_api_call(lambda: load_quiz_data_from_dedicated_sheet(student_name), fallback_value=pd.DataFrame())

def cached_calculate_attendance_rate(student_id, student_name):
    from utils.g_sheets import get_all_logs
    df_all_logs_raw = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

    if df_all_logs_raw.empty or '出欠' not in df_all_logs_raw.columns or "APIエラー発生" in df_all_logs_raw.columns:
        return "データなし"
        
    df_all_logs = df_all_logs_raw.copy()
    
    if student_id != "未設定" and '生徒ID' in df_all_logs.columns:
        df_student = df_all_logs[df_all_logs['生徒ID'].astype(str) == str(student_id)]
    else:
        name_col = '名前' if '名前' in df_all_logs.columns else '生徒名'
        if name_col in df_all_logs.columns:
            df_student = df_all_logs[df_all_logs[name_col] == student_name]
        else:
            return "データなし"

    if df_student.empty:
        return "0% (履歴なし)"
        
    attend_keywords = ['出席（通常）', '出席（振替授業を消化）']
    absent_keywords = ['欠席（後日振替あり）', '欠席（振替なし）']
    records = df_student['出欠'].dropna().astype(str)
    attend_count = records.isin(attend_keywords).sum()
    absent_count = records.isin(absent_keywords).sum()
    total_lessons = attend_count + absent_count
    
    if total_lessons == 0: return "0% (履歴なし)"
    rate = (attend_count / total_lessons) * 100
    return f"{int(rate)}%"

@st.cache_data(ttl=600, show_spinner=False)
def cached_calculate_homework_rate(student_id, student_name):
    from utils.g_sheets import get_all_logs
    df_all_logs_raw = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

    if df_all_logs_raw.empty or "APIエラー発生" in df_all_logs_raw.columns:
        return "データなし"
        
    df_all_logs = df_all_logs_raw.copy()
    
    if student_id != "未設定" and '生徒ID' in df_all_logs.columns:
        df_student = df_all_logs[df_all_logs['生徒ID'].astype(str) == str(student_id)]
    else:
        name_col = '名前' if '名前' in df_all_logs.columns else '生徒名'
        if name_col in df_all_logs.columns:
            df_student = df_all_logs[df_all_logs[name_col] == student_name]
        else:
            return "データなし"

    if df_student.empty:
        return "100% (履歴なし)"
        
    if '出した宿題P' not in df_student.columns or 'やった宿題P' not in df_student.columns:
        return "データなし"

    assigned = pd.to_numeric(df_student['出した宿題P'], errors='coerce').fillna(0)
    done = pd.to_numeric(df_student['やった宿題P'], errors='coerce').fillna(0)
    
    total_assigned = assigned.sum()
    total_done = done.sum()
    
    if total_assigned == 0:
        return "100% (宿題なし)"
        
    rate = (total_done / total_assigned) * 100
    rate = min(rate, 100.0) 
    
    return f"{int(rate)}%"

def cached_get_student_master_for_report():
    from utils.g_sheets import get_student_master
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def cached_get_quiz_details_for_report():
    from utils.g_sheets import get_quiz_master_dict
    return robust_api_call(get_quiz_master_dict, fallback_value={})

# ==========================================
# 🎯 面談レポート画面のメイン関数
# ==========================================
def render_conference_report(selected_student_option, info):
    
    if " - " in selected_student_option:
        student_id = selected_student_option.split(" - ")[0]
        student_name = selected_student_option.split(" - ")[1]
    else:
        student_id = "未設定"
        student_name = selected_student_option
        
    if student_id == "未設定" and "生徒ID" in info:
        student_id = str(info["生徒ID"]).strip()

    if not info:
        df_students_raw = cached_get_student_master_for_report()
        df_students = df_students_raw.copy()
        if not df_students.empty and '生徒名' in df_students.columns:
            student_row = df_students[df_students['生徒名'] == student_name]
            if not student_row.empty:
                info = student_row.iloc[0].to_dict()

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
        st.header(f"🎓 {student_name} さん 面談レポート") 
    with col_print:
        if st.button("🖨️ レポートを印刷"):
            components.html("<script>window.parent.print();</script>", height=0)

    st.caption("※データ読み込み専用画面です。通信エラーを防ぐため一時保存データを表示しています。")

    with st.spinner("学習データを集計中..."):
        master_dict = cached_get_textbook_master()
        df_quiz = cached_load_quiz_data(student_name)
        df_test_all = safe_load_test_scores()
        df_monthly_ss = cached_load_self_study_by_student(student_name)
        quiz_details = cached_get_quiz_details_for_report() 

    df_student_tests = pd.DataFrame()
    if not df_test_all.empty and "APIエラー発生" not in df_test_all.columns:
        df_student_tests = df_test_all[df_test_all['生徒名'] == student_name]

    st.divider()

    # ==========================================
    # 1. 宿題・出席・努力の量
    # ==========================================
    st.subheader("🔥 学習への取り組み姿勢")
    col1, col2, col3, col4 = st.columns(4)
    
    with st.spinner("出席率・宿題進捗を計算中..."):
        attendance_rate = cached_calculate_attendance_rate(student_id, student_name)
        hw_rate_str = cached_calculate_homework_rate(student_id, student_name)
    
    try:
        hw_rate = float(hw_rate_str.replace('%', '').split()[0])
    except Exception:
        hw_rate = 0.0

    col1.metric("🏠 宿題履行率", hw_rate_str)
    col2.metric("📅 出席率", attendance_rate)
    
    total_quiz_attempts = len(df_quiz) if not df_quiz.empty else 0
    col3.metric("📝 小テスト総回数", f"{total_quiz_attempts} 回")
    
    target_goal = "未設定"
    for key, value in info.items():
        if "志望校" in str(key) or "目的" in str(key) or "目標" in str(key):
            val_str = str(value).strip()
            if val_str and val_str.lower() != "nan":
                target_goal = val_str
                break
                
    col4.metric("🎯 志望校・目標", target_goal)

    st.write("#### 📅 月別の自習時間（努力の可視化）")
    if not df_monthly_ss.empty:
        ss_chart = alt.Chart(df_monthly_ss).mark_bar(
            cornerRadiusEnd=4, 
            color='#ff7f0e', 
            size=20
        ).encode(
            x=alt.X('自習時間(分):Q', title='合計自習時間 (分)'),
            y=alt.Y('年月:N', title='月', sort=None),
            tooltip=['年月', '自習時間(分)']
        ).properties(height=200)

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
    # 2. 学校成績の推移
    # ==========================================
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
    # 3. 小テスト進捗の一覧 ＆ カラーマップ
    # ==========================================
    st.subheader("📊 小テスト（基礎学力）の定着状況")
    
    st.markdown("**【合格の基準について】**")
    st.caption("各単元の小テストにおいて、満点に対する**正答率が80%以上**を獲得したものを「合格（定着済み）」として進捗にカウントしています。")
    st.write("") 

    if not df_quiz.empty:
        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz['正答率'] = df_quiz.apply(lambda row: calculate_score_ratio(row, quiz_details), axis=1)

    if master_dict is not None and not df_quiz.empty: 
        summary_data = []
        attempted_texts = df_quiz['テキスト'].dropna().unique()
        
        for text_name in attempted_texts:
            df_text = df_quiz[(df_quiz['テキスト'] == text_name) & (df_quiz['正答率'] >= 0.8)]
            done_chaps = df_text['単元'].nunique() if '単元' in df_text.columns else 0
            
            if text_name in master_dict:
                chaps = master_dict[text_name]
                total_chaps = len(chaps)
                progress = int((done_chaps / total_chaps) * 100) if total_chaps > 0 else 0
                display_chaps = f"{done_chaps} / {total_chaps} 章"
            else:
                total_attempted = df_quiz[df_quiz['テキスト'] == text_name]['単元'].nunique()
                progress = int((done_chaps / total_attempted) * 100) if total_attempted > 0 else 0
                display_chaps = f"{done_chaps} / {total_attempted} 章 (マスタ未登録)"
                
            summary_data.append({
                "テキスト名": text_name,
                "進捗率(%)": progress,
                "合格章数": display_chaps
            })
            
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            dynamic_height = max(200, len(df_summary) * 40)
            
            bar_chart = alt.Chart(df_summary).mark_bar().encode(
                x=alt.X('進捗率(%):Q', scale=alt.Scale(domain=[0, 100])),
                y=alt.Y('テキスト名:N', sort='-x'),
                color=alt.Color('進捗率(%):Q', scale=alt.Scale(scheme='blues')),
                tooltip=['テキスト名', '進捗率(%)', '合格章数']
            ).properties(height=dynamic_height) 
            
            st.altair_chart(bar_chart, use_container_width=True)
        else:
            st.info("集計できる小テストデータがありません。")
    else:
        st.info("小テストのデータがまだありません。")

    # ==========================================
    # 🌟 NEW: 学年横断カラーマップ（ヒートマップ） - 完全版
    # ==========================================
    st.write("---")
    st.markdown("#### 🗺️ 学年横断カラーマップ（弱点分析ヒートマップ）")
    st.write("積み上げ科目の弱点分析に最適です。横並びで定着度を比較できます。")
    st.caption("🟩 80%以上 (合格) / 🟨 60~79% (要復習) / 🟥 60%未満 (苦手) / ⬜ 未実施")

    available_texts = set()
    if master_dict: available_texts.update(master_dict.keys())
    if not df_quiz.empty and 'テキスト' in df_quiz.columns:
        available_texts.update(df_quiz['テキスト'].dropna().unique())
        
    all_texts_options = ["未選択"] + sorted(list(available_texts))

    num_texts = st.selectbox("比較するテキストの数を選択", [1, 2, 3, 4, 5], index=2)
    
    cols = st.columns(num_texts)
    selected_texts_raw = []
    
    for i in range(num_texts):
        with cols[i]:
            t_val = st.selectbox(f"比較テキスト {i+1}", all_texts_options, key=f"cm_t{i}")
            selected_texts_raw.append(t_val)

    selected_texts = []
    for t in selected_texts_raw:
        if t != "未選択" and t not in selected_texts:
            selected_texts.append(t)

    if selected_texts:
        max_chaps = 0
        text_chap_maps = {}
        for t in selected_texts:
            chaps = master_dict.get(t, {})
            text_chap_maps[t] = chaps
            if chaps:
                int_keys = [int(k) for k in chaps.keys() if str(k).isdigit()]
                if int_keys: max_chaps = max(max_chaps, max(int_keys))
            else:
                if not df_quiz.empty:
                    quiz_chaps = df_quiz[df_quiz['テキスト'] == t]['単元'].dropna().astype(str)
                    int_quiz_chaps = [int(k) for k in quiz_chaps if k.isdigit()]
                    if int_quiz_chaps: max_chaps = max(max_chaps, max(int_quiz_chaps))
        
        if max_chaps == 0: max_chaps = 15

        map_data = []
        style_data = []
        
        for i in range(1, max_chaps + 1):
            row = {"縦軸(章)": f"第{i}章"}
            style_row = {"縦軸(章)": "font-weight: bold; background-color: #f0f2f6; text-align: center;"}
            
            for t in selected_texts:
                chap_name = text_chap_maps[t].get(str(i), "-")
                score_disp = "-"
                cell_style = "" 
                
                if not df_quiz.empty:
                    df_target = df_quiz[(df_quiz['テキスト'] == t) & (df_quiz['単元'].astype(str) == str(i))]
                    df_target = df_target.dropna(subset=['正答率'])
                    
                    if not df_target.empty:
                        idx_max = df_target['正答率'].idxmax()
                        best_ratio = df_target.loc[idx_max, '正答率']
                        best_score_raw = df_target.loc[idx_max, '点数']
                        
                        try:
                            score_val = int(float(best_score_raw))
                        except:
                            score_val = best_score_raw
                            
                        score_disp = f"{score_val}"
                        
                        if best_ratio >= 0.8:
                            cell_style = "background-color: #c6efce; color: #006100; font-weight: bold; text-align: center;" 
                        elif best_ratio >= 0.6:
                            cell_style = "background-color: #ffeb9c; color: #9c5700; font-weight: bold; text-align: center;" 
                        else:
                            cell_style = "background-color: #ffc7ce; color: #9c0006; font-weight: bold; text-align: center;" 

                row[f"{t} (単元名)"] = chap_name
                row[f"点数 ({t})"] = score_disp
                
                style_row[f"{t} (単元名)"] = ""
                style_row[f"点数 ({t})"] = cell_style
                
            map_data.append(row)
            style_data.append(style_row)

        df_map = pd.DataFrame(map_data)
        df_style = pd.DataFrame(style_data)
        
        styler = df_map.style.apply(lambda _: df_style, axis=None)
        
        st.dataframe(styler, use_container_width=True, hide_index=True)
        
        st.write("") 
        col_dl, col_blank = st.columns([1, 2])
        with col_dl:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                styler.to_excel(writer, index=False, sheet_name='弱点分析マップ')
            
            excel_data = excel_buffer.getvalue()
            
            # 🌟 変更: ファイル名を動的にカスタマイズ！
            # 選択されたテキスト名をアンダーバーで繋ぐ
            texts_joined = "_".join(selected_texts)
            # ファイル名に使えない記号（/や\など）を安全のため全角に変換するか削除する
            texts_for_filename = re.sub(r'[\\/:*?"<>|]', ' ', texts_joined)
            
            # 生徒ID_生徒名_選択テキスト_カラーマップ.xlsx という美しい名前に！
            dynamic_file_name = f"{student_id}_{student_name}_{texts_for_filename}_カラーマップ.xlsx"
            
            st.download_button(
                label="📥 この表をExcel形式（色付き）でダウンロード",
                data=excel_data,
                file_name=dynamic_file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
            
    else:
        st.info("👆 上のドロップダウンから、比較したいテキストを選択してください。")

    st.divider()

    # ==========================================
    # 4. 弱点分析
    # ==========================================
    st.subheader("💡 優先して復習すべき単元（自動ピックアップ）")
    if not df_quiz.empty:
        df_weak = df_quiz[df_quiz['正答率'] < 0.6].sort_values(by='日時', ascending=False).head(5)
        
        if not df_weak.empty:
            st.write("以下の単元は、直近のテストで点数が伸び悩んだため、次回の授業や講習で優先的に対策を行います。")
            
            def format_weak_unit(row):
                t_name = str(row.get('テキスト', ''))
                chap_str = str(row.get('単元', ''))
                
                t_master = master_dict.get(t_name, {})
                chap_name = t_master.get(chap_str, "")
                
                if chap_name:
                    return f"{chap_str}: {chap_name}"
                else:
                    return f"第{chap_str}回"
                    
            df_weak['単元'] = df_weak.apply(format_weak_unit, axis=1)
            
            desired_columns = ['日時', 'テキスト', '単元', '点数', 'ミス番号', '間違えた問題', 'ミス問題番号', 'ミス']
            available_columns = [col for col in desired_columns if col in df_weak.columns]
            
            display_weak = df_weak[available_columns]
            
            if '日時' in display_weak.columns:
                st.table(display_weak.set_index("日時"))
            else:
                st.table(display_weak)
        else:
            st.success("現在、極端に正答率が低い（苦手な）単元は見当たりません！順調です。")