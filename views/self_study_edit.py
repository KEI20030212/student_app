# views/self_study_edit.py

import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import load_self_study_data, update_self_study_record, delete_self_study_record
from utils.api_guard import robust_api_call

def render_self_study_edit_page():
    st.info("💡 過去の自習記録を呼び出して、内容（時間や科目など）を直接修正・上書き保存、または削除できます。")

    col1, col2, col_r = st.columns([2, 3, 1])
    target_date = col1.date_input("📅 修正したい自習の日付", datetime.date.today(), key="ss_edit_date")

    with col_r:
        st.write("") 
        st.write("") 
        if st.button("🔄 データを更新", use_container_width=True, key="ss_edit_refresh"):
            st.cache_data.clear() # 🌟 修正：全体のキャッシュを強制クリアして最新化
            st.rerun() 

    with st.spinner("自習記録を検索中..."):
        df_ss = robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())

    if df_ss.empty or 'APIエラー発生' in df_ss.columns:
        st.warning("データが取得できませんでした。")
        return

    # 日付列の名前ゆれに対応
    date_col = '日付' if '日付' in df_ss.columns else '日時' if '日時' in df_ss.columns else None
    name_col = '名前' if '名前' in df_ss.columns else '生徒名' if '生徒名' in df_ss.columns else None
    
    if not date_col or not name_col:
        st.error("スプレッドシートに「日付（または日時）」や「名前」列が見つかりません。")
        return

    # 指定された日付のデータのみ抽出
    date_str = target_date.strftime("%Y/%m/%d")
    df_filtered = df_ss[df_ss[date_col].astype(str).str.contains(date_str, na=False)]

    if df_filtered.empty:
        st.warning(f"{date_str} の自習記録は見つかりませんでした。")
        return

    options = []
    for idx, row in df_filtered.iterrows():
        s_name = str(row.get(name_col, '不明'))
        s_time = str(row.get('開始時間', ''))
        e_time = str(row.get('終了時間', ''))
        sub = str(row.get('教科', ''))
        
        opt_label = f"👤 {s_name} | ⌚ {s_time}〜{e_time} | 📚 {sub}"
        options.append((idx, opt_label))

    selected_opt = col2.selectbox("📝 修正する自習記録を選択", options, format_func=lambda x: x[1], key="ss_edit_select")

    if selected_opt:
        idx = selected_opt[0]
        record = df_filtered.loc[idx]
        student_name = record.get(name_col)

        st.divider()
        st.write(f"### ✍️ {student_name} さんの自習記録を修正")

        with st.form("edit_ss_form"):
            st.write("📋 **時間と科目の修正**")
            
            c_d, c_s, c_e, c_b = st.columns([1.5, 1.2, 1.2, 1])
            
            # 日付の復元
            try: orig_date = pd.to_datetime(str(record.get(date_col))).date()
            except: orig_date = target_date
            new_date = c_d.date_input("📅 日付", orig_date, key="edit_ss_d")
            
            # 時間の復元
            def parse_time(time_str, default_time):
                try: return pd.to_datetime(str(time_str)).time()
                except: return default_time
                
            orig_start = parse_time(record.get('開始時間'), datetime.time(17, 0))
            orig_end = parse_time(record.get('終了時間'), datetime.time(19, 0))
            
            new_start = c_s.time_input("🛫 開始時間", orig_start, key="edit_ss_start")
            new_end = c_e.time_input("🛬 終了時間", orig_end, key="edit_ss_end")
            
            # 休憩時間の復元
            orig_break = str(record.get('休憩時間', 0)).replace('分', '').strip()
            new_break = c_b.number_input("☕ 休憩時間(分)", value=int(orig_break) if orig_break.isdigit() else 0, step=5, key="edit_ss_break")
            
            # 実質勉強時間の自動計算表示用
            start_dt = datetime.datetime.combine(new_date, new_start)
            end_dt = datetime.datetime.combine(new_date, new_end)
            diff_min = (end_dt - start_dt).seconds // 60
            if end_dt < start_dt: diff_min = 0
            actual_min = max(0, diff_min - new_break)
            pts = int(actual_min // 30)
            
            st.caption(f"💡 修正後の計算: 実質勉強時間 **{actual_min}分** （獲得: {pts}pt）")

            c_sub, c_memo = st.columns([1, 2])
            sub_opts = ["英語", "数学", "国語", "理科", "社会", "その他"]
            curr_sub = str(record.get('教科', 'その他'))
            if curr_sub not in sub_opts: sub_opts.append(curr_sub)
            new_sub = c_sub.selectbox("📚 教科", sub_opts, index=sub_opts.index(curr_sub), key="edit_ss_sub")
            
            new_memo = c_memo.text_area("📖 学習内容", value=str(record.get('内容', '')), height=68, key="edit_ss_memo")

            submitted = st.form_submit_button("💾 修正を上書き保存する", type="primary", use_container_width=True)

            if submitted:
                target_data = {
                    "名前": student_name,
                    "日付": str(record.get(date_col)),
                    "開始時間": str(record.get('開始時間'))
                }
                
                new_data = {
                    "日付": new_date.strftime("%Y/%m/%d"),
                    "開始時間": new_start.strftime("%H:%M"),
                    "終了時間": new_end.strftime("%H:%M"),
                    "休憩時間": new_break,
                    "実質": actual_min,
                    "教科": new_sub,
                    "内容": new_memo,
                    "獲得pt": pts
                }
                
                with st.spinner("データを上書き保存中..."):
                    success = robust_api_call(update_self_study_record, target_data, new_data, fallback_value=False)
                    if success:
                        st.success("✅ 自習記録の修正を保存しました！")
                        st.cache_data.clear() # 🌟 修正：全体のキャッシュを強制クリア
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 更新に失敗しました。対象のデータが見つからないか、通信エラーです。")

        # --- 🗑️ 削除エリア ---
        st.write("")
        st.write("▼ この記録を削除する場合は、チェックを入れてからボタンを押してください")
        del_check = st.checkbox("本当に削除する", key="edit_ss_del_chk")
        
        if del_check:
            if st.button("🗑️ 削除を実行", type="secondary"):
                target_data = {
                    "名前": student_name,
                    "日付": str(record.get(date_col)),
                    "開始時間": str(record.get('開始時間'))
                }
                with st.spinner("スプレッドシートから削除中..."):
                    success = robust_api_call(delete_self_study_record, target_data, fallback_value=False)
                    if success:
                        st.success("✅ 削除しました！")
                        st.cache_data.clear() # 🌟 修正：全体のキャッシュを強制クリア
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 削除に失敗しました。")