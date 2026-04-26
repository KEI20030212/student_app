import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 🌟 utils/g_sheets.py から新しい専用関数を呼び出し
# ==========================================
from utils.g_sheets import (
    get_all_student_names, 
    get_textbook_master,
    save_quiz_to_dedicated_sheet,        # 新しく追加した保存用関数
    load_quiz_data_from_dedicated_sheet  # 新しく追加した読込用関数
)

# ==========================================
# 🌟 APIエラー対策：キャッシュ（一時保存）機能
# ==========================================
@st.cache_data(ttl=600)  # 600秒(10分)間は再取得せず、手元のデータを使い回す
def cached_get_student_names():
    return get_all_student_names()

@st.cache_data(ttl=600)  # マスタデータも10分間キャッシュ
def cached_get_textbook_master():
    return get_textbook_master()

@st.cache_data(ttl=60)   # 小テスト記録データのキャッシュ
def cached_load_quiz_data(student_name):
    return load_quiz_data_from_dedicated_sheet(student_name)

# ==========================================

def render_quiz_list_page():
    st.header("📝 小テスト進捗＆習熟度マップ")
    st.write("縦軸がテキスト、横軸が章です。授業以外で実施したテスト結果もここから入力できます🎨")

    # 1. 生徒の選択
    student_names = cached_get_student_names()
    selected_student = st.selectbox("👤 生徒を選択", ["-- 選択 --"] + student_names)
    
    if selected_student == "-- 選択 --":
        st.stop()

    # マスタデータの読み込み
    master_dict = cached_get_textbook_master()

    # ==========================================
    # 🌟 【新機能】小テスト結果の入力フォーム
    # ==========================================
    with st.expander("📝 小テスト結果を登録する（授業以外・自習など）"):
        st.write(f"**{selected_student}** さんのテスト結果を入力します。")
        
        with st.form("quiz_input_form"):
            col1, col2 = st.columns(2)
            
            # テキスト選択
            textbooks = list(master_dict.keys())
            target_text = col1.selectbox("📚 テキスト", textbooks)
            
            # 章の選択（選択したテキストに基づいてリストを変える）
            chapters = master_dict.get(target_text, [])
            target_chap = col2.selectbox("📖 章・単元", chapters)
            
            col3, col4 = st.columns(2)
            # 🌟 ミス問題番号の入力
            w_nums = col3.text_input("❌ ミス問題番号 (カンマ区切りで入力)", placeholder="例: 1, 3, 5")
            # 実施日
            test_date = col4.date_input("📅 実施日", datetime.date.today())
            
            submit_quiz = st.form_submit_button("この内容で記録する ✨", type="primary")
            
            if submit_quiz:
                # 🌟 点数の自動計算 (ミス1問につき-10点)
                if not w_nums.strip():
                    score = 100
                    miss_count = 0
                else:
                    miss_count = len([x for x in w_nums.split(",") if x.strip()])
                    score = max(0, 100 - (miss_count * 10))

                with st.spinner("記録中..."):
                    # 🌟 専用シート用の関数に変更！(実施形態は"自習"として記録)
                    success = save_quiz_to_dedicated_sheet(
                        test_date.strftime("%Y/%m/%d"), 
                        selected_student, 
                        target_text, 
                        target_chap, 
                        score,
                        w_nums,
                        "自習"
                    )
                    
                    if success:
                        st.success(f"【{target_text} {target_chap}】を {score}点（ミス{miss_count}問）で記録しました！")
                        # キャッシュをクリアして最新データを読み込めるようにする
                        cached_load_quiz_data.clear()
                        # 画面を更新してグラフに反映
                        st.rerun()
                    else:
                        st.error("記録に失敗しました。スプレッドシートを確認してください。")

    st.divider()

    # ==========================================
    # 🌟 以降、習熟度マップの表示ロジック
    # ==========================================
    with st.spinner("習熟度データを集計中..."):
        # 🌟 ここも専用シートから読み込むように変更！
        df_quiz = cached_load_quiz_data(selected_student)
        
        flat_data = []
        for text_name, chaps in master_dict.items():
            for chap in chaps:
                flat_data.append({'テキスト': text_name, '章': chap})
                
        df_master = pd.DataFrame(flat_data, columns=['テキスト', '章'])

        if df_master.empty:
            st.warning("⚠️ マスタデータが読み込めませんでした。")
            st.stop()

        if df_quiz.empty:
            st.warning("小テストの記録がまだありません。")
            st.stop()

        # 点数を数値に変換
        df_quiz['点数'] = pd.to_numeric(df_quiz['点数'], errors='coerce')
        df_quiz = df_quiz.dropna(subset=['点数']).copy()

        # 3. 前回小テスト日の表示
        if not df_quiz.empty:
            df_quiz['日時'] = pd.to_datetime(df_quiz['日時'], format='mixed', errors='coerce')
            last_date = df_quiz['日時'].max().strftime("%Y年%m月%d日")
            st.success(f"📅 前回小テスト実施日: **{last_date}**")
        else:
            st.info("📅 まだ小テストの記録がありません。")

        # 4. マスタと合体
        best_scores = df_quiz.groupby(['テキスト', '単元'])['点数'].max().reset_index()
        best_scores = best_scores.rename(columns={'単元': '章', '点数': '最高点数'})

        df_master['章_clean'] = df_master['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()
        best_scores['章_clean'] = best_scores['章'].astype(str).str.replace('第', '').str.replace('章', '').str.strip()

        df_merged = pd.merge(df_master, best_scores, left_on=['テキスト', '章_clean'], right_on=['テキスト', '章_clean'], how='left', suffixes=('', '_score'))

        # 🌟 タブの生成
        textbook_names = df_master['テキスト'].unique().tolist()
        
        if not textbook_names:
            st.warning("テキスト一覧が見つかりません。")
            st.stop()

        tabs = st.tabs(textbook_names)

        # 各テキストごとにタブの中身を作っていく
        for i, text_name in enumerate(textbook_names):
            with tabs[i]: 
                df_text = df_merged[df_merged['テキスト'] == text_name]
                
                # --- 🎯 達成率の計算 ---
                total_chaps = len(df_text)
                done_chaps = df_text['最高点数'].notna().sum()
                
                if total_chaps > 0:
                    progress_rate = int((done_chaps / total_chaps) * 100)
                else:
                    progress_rate = 0
                
                st.subheader(f"📊 達成率: {progress_rate}% ({done_chaps}/{total_chaps}章クリア)")
                st.progress(progress_rate / 100.0)
                st.write("") 

                # --- 🎨 表の作成 ---
                pivot_df = df_text.pivot_table(
                    index='テキスト', 
                    columns='章', 
                    values='最高点数', 
                    aggfunc='max'
                )
                
                if pivot_df.empty:
                    st.info("このテキストのテスト記録はまだありません。")
                    continue
                
                import re
                def sort_chapter_key(col_name):
                    nums = re.findall(r'\d+', str(col_name))
                    if nums:
                        return int(nums[0])
                    return 9999

                sorted_cols = sorted(pivot_df.columns.tolist(), key=sort_chapter_key)
                pivot_df = pivot_df[sorted_cols]

                # --- ✨ アイコン化＆カラーリング ---
                def add_icon_to_score(val):
                    if pd.isna(val) or val == "":
                        return ""
                    try:
                        v = float(val)
                        if v == 100: return f"👑 100"
                        elif v >= 80: return f"🟢 {int(v)}"
                        elif v >= 60: return f"🟡 {int(v)}"
                        else: return f"🔴 {int(v)}"
                    except:
                        return str(val)

                display_df = pivot_df.copy()
                for col in display_df.columns:
                    display_df[col] = display_df[col].map(add_icon_to_score)

                def color_score_bg(val):
                    val_str = str(val)
                    if "👑" in val_str:
                        return 'background-color: #fffacd; color: #000000; font-weight: bold;'
                    elif "🟢" in val_str:
                        return 'background-color: #c6efce; color: #006100; font-weight: bold;'
                    elif "🟡" in val_str:
                        return 'background-color: #ffeb9c; color: #9c6500; font-weight: bold;'
                    elif "🔴" in val_str:
                        return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold;'
                    return ''

                try:
                    styled_df = display_df.style.map(color_score_bg)
                except AttributeError:
                    styled_df = display_df.style.applymap(color_score_bg)
                
                st.dataframe(styled_df, use_container_width=True)