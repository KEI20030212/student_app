import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import (
    get_all_logs, 
    update_lesson_record_in_sheet,
    load_quiz_records,            
    get_quiz_master_dict,         
    update_quiz_record_in_sheet   
)
from utils.api_guard import robust_api_call

def render_edit_input_page():
    st.info("💡 過去の授業記録を呼び出して、内容を直接修正・上書き保存できます。")

    col1, col2 = st.columns(2)
    target_date = col1.date_input("📅 修正したい授業の日付", datetime.date.today())

    with st.spinner("記録を検索中..."):
        df_logs = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

    if df_logs.empty or 'APIエラー発生' in df_logs.columns:
        st.warning("データが取得できませんでした。")
        return

    date_str = target_date.strftime("%Y/%m/%d")
    if '日時' in df_logs.columns:
        df_filtered = df_logs[df_logs['日時'].astype(str).str.contains(date_str, na=False)]
    else:
        st.error("スプレッドシートに「日時」列が見つかりません。")
        return

    if df_filtered.empty:
        st.warning(f"{date_str} の授業記録は見つかりませんでした。")
        return

    options = []
    for idx, row in df_filtered.iterrows():
        opt_label = f"{row.get('名前', '不明')} - {row.get('科目', '不明')} ({row.get('授業コマ', '不明')})"
        options.append((idx, opt_label))

    selected_opt = col2.selectbox("📝 修正する記録を選択", options, format_func=lambda x: x[1])

    if selected_opt:
        idx = selected_opt[0]
        record = df_filtered.loc[idx]

        st.divider()
        st.write(f"### ✍️ {record.get('名前')} さんの記録を修正")

        with st.form("edit_record_form"):
            c1, c2, c3 = st.columns(3)
            
            att_opts = ["出席（通常）", "出席（振替授業を消化）", "欠席（後日振替あり）", "欠席（振替なし）"]
            current_att = record.get('出欠', '出席（通常）')
            new_att = c1.selectbox("📅 出欠状況", att_opts, index=att_opts.index(current_att) if current_att in att_opts else 0)
            
            sub_opts = ["英語", "数学", "国語", "理科", "社会"]
            current_sub = record.get('科目', '英語')
            new_sub = c2.selectbox("科目", sub_opts, index=sub_opts.index(current_sub) if current_sub in sub_opts else 0)
            
            current_late = str(record.get('遅刻時間', 0)).replace('分', '')
            new_late = c3.number_input("⏰ 遅刻時間 (分)", value=int(current_late) if current_late.isdigit() else 0, step=5)

            st.write("📚 **授業進捗・宿題（直接テキストを編集できます）**")
            st.caption("※複雑なページ数も、ここのテキストを直接書き換えるだけで簡単に修正・上書きが可能です。")
            
            c_txt1, c_txt2 = st.columns(2)
            with c_txt1:
                new_used_text = st.text_area("📘 今回使用したテキスト", value=str(record.get('テキスト', '')), height=68)
                new_adv = st.text_area("📖 授業進捗 (P.〇〜〇)", value=str(record.get('終了ページ', '')), height=68)
            with c_txt2:
                new_hw_text = st.text_area("📘 次回の宿題テキスト", value=str(record.get('次回の宿題テキスト', '')), height=68)
                new_hw = st.text_area("🚀 次回の宿題範囲 (P.〇〜〇)", value=str(record.get('次回の宿題ページ数', '')), height=68)

            # 🌟 追加：宿題未達成の理由と修正策の編集UI
            st.write("⚠️ **宿題未達成の理由と修正策**")
            c_hw_r1, c_hw_r2 = st.columns(2)
            
            reason_opts = ["", "難易度(難しかった)", "文量(多かった)", "時間管理(サボり・多忙)", "事故(体調・急用)", "その他"]
            fix_opts = ["", "文量調整(減らす)", "期限延長(スライド)", "内容変更(基礎へ戻る)", "再約束(マインドセット)", "その他"]
            
            # 既存のデータを取得してインデックスを判定（「その他:〇〇」の場合は「その他」を選択状態にする）
            curr_reason = str(record.get('未達成の理由', '')).strip()
            if curr_reason == "nan": curr_reason = ""
            reason_idx = reason_opts.index(curr_reason) if curr_reason in reason_opts else (5 if curr_reason else 0)
            
            curr_fix = str(record.get('本日の修正策', '')).strip()
            if curr_fix == "nan": curr_fix = ""
            fix_idx = fix_opts.index(curr_fix) if curr_fix in fix_opts else (5 if curr_fix else 0)

            with c_hw_r1:
                new_reason_sel = st.selectbox("未達成の理由", reason_opts, index=reason_idx)
                if new_reason_sel == "その他":
                    default_reason_other = curr_reason.replace("その他: ", "") if "その他" in curr_reason else curr_reason
                    new_reason_other = st.text_input("理由（その他）", value=default_reason_other)
                    final_reason = f"その他: {new_reason_other}" if new_reason_other else "その他"
                else:
                    final_reason = new_reason_sel

            with c_hw_r2:
                new_fix_sel = st.selectbox("本日の修正策", fix_opts, index=fix_idx)
                if new_fix_sel == "その他":
                    default_fix_other = curr_fix.replace("その他: ", "") if "その他" in curr_fix else curr_fix
                    new_fix_other = st.text_input("修正策（その他）", value=default_fix_other)
                    final_fix = f"その他: {new_fix_other}" if new_fix_other else "その他"
                else:
                    final_fix = new_fix_sel

            st.divider()
            st.write("💯 **実施した小テストの修正**")
            
            df_quizzes = robust_api_call(load_quiz_records, fallback_value=pd.DataFrame())
            quiz_details = robust_api_call(get_quiz_master_dict, fallback_value={})
            
            day_quizzes = []
            if not df_quizzes.empty and '名前' in df_quizzes.columns and '日時' in df_quizzes.columns:
                mask = (df_quizzes['名前'] == record.get('名前')) & (df_quizzes['日時'].astype(str).str.startswith(date_str))
                day_quizzes = df_quizzes[mask].to_dict('records')
            
            edited_quizzes = []
            if day_quizzes:
                for q_idx, q in enumerate(day_quizzes):
                    q_name = q.get('テキスト', '不明') 
                    old_unit = q.get('単元', 1)
                    old_score = q.get('点数', 100)
                    
                    current_max = 100
                    matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_name}_")]
                    if matched_marks:
                        current_max = int(pd.Series(matched_marks).mode()[0])
                        
                    st.caption(f"📝 **{q_name}**")
                    col_q1, col_q2 = st.columns(2)
                    with col_q1:
                        new_unit = st.number_input(f"単元/回", value=int(old_unit) if str(old_unit).isdigit() else 1, key=f"edit_q_unit_{q_idx}")
                    with col_q2:
                        safe_old_score = int(old_score) if str(old_score).isdigit() else 0
                        safe_max = max(current_max, safe_old_score)
                        new_score = st.number_input(f"点数 (/{current_max}点満点)", min_value=0, max_value=safe_max, value=safe_old_score, key=f"edit_q_score_{q_idx}")
                    
                    edited_quizzes.append({
                        "quiz_name": q_name,
                        "old_unit": old_unit,
                        "new_unit": new_unit,
                        "old_score": old_score,
                        "new_score": new_score
                    })
            else:
                st.info("この日の小テスト記録はありません。")

            st.divider()
            st.write("🧠 **授業中の様子・評価**")
            c_eval1, c_eval2 = st.columns(2)
            eval_opts = ["超集中", "前向き", "疲労気味", "ムラあり", "集中できない"]
            reac_opts = ["原因を分析した", "悔しがった", "放置しようとした"]
            
            current_conc = record.get('集中力', '前向き')
            current_reac = record.get('ミスへの反応', '原因を分析した')
            new_conc = c_eval1.selectbox("集中力", eval_opts, index=eval_opts.index(current_conc) if current_conc in eval_opts else 0)
            new_reac = c_eval2.selectbox("ミスへの反応", reac_opts, index=reac_opts.index(current_reac) if current_reac in reac_opts else 0)

            st.write("💬 **コメント事項**")
            new_advc = st.text_area("🗣️ 授業でのアドバイス", value=str(record.get('アドバイス', '')), height=100)
            new_pmsg = st.text_area("👪 保護者への連絡事項", value=str(record.get('保護者への連絡', '')), height=100)
            new_next_h = st.text_area("🔄 次回への引継ぎ事項", value=str(record.get('次回への引継ぎ', '')), height=100)

            submitted = st.form_submit_button("💾 修正を上書き保存する", type="primary", use_container_width=True)

            if submitted:
                with st.spinner("データを上書き保存中..."):
                    update_data = {
                        "出欠": new_att,
                        "科目": new_sub,
                        "遅刻時間": new_late,
                        "テキスト": new_used_text,
                        "終了ページ": new_adv,
                        "次回の宿題テキスト": new_hw_text,
                        "次回の宿題ページ数": new_hw,
                        "集中力": new_conc,
                        "ミスへの反応": new_reac,
                        "アドバイス": new_advc,
                        "保護者への連絡": new_pmsg,
                        "次回への引継ぎ": new_next_h,
                        "未達成の理由": final_reason, # 🌟 追加
                        "本日の修正策": final_fix    # 🌟 追加
                    }
                    
                    success_main = robust_api_call(
                        update_lesson_record_in_sheet,
                        date_str=date_str,
                        student_name=record.get('名前'),
                        class_slot=record.get('授業コマ'),
                        new_data=update_data,
                        fallback_value=False
                    )

                    for eq in edited_quizzes:
                        if str(eq['old_unit']) != str(eq['new_unit']) or str(eq['old_score']) != str(eq['new_score']):
                            robust_api_call(
                                update_quiz_record_in_sheet,
                                date_str=date_str,
                                student_name=record.get('名前'),
                                quiz_name=eq['quiz_name'],
                                old_unit=eq['old_unit'],
                                new_unit=eq['new_unit'],
                                new_score=eq['new_score'],
                                fallback_value=False
                            )

                    if success_main:
                        st.success("✅ 授業記録と小テストの修正を保存しました！")
                        st.cache_data.clear()
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 更新に失敗しました。対象のデータが見つからないか、通信エラーです。")