import streamlit as st
import pandas as pd
import datetime
import time
from utils.g_sheets import get_all_logs, update_lesson_record_in_sheet
from utils.api_guard import robust_api_call

def render_edit_input_page():
    st.info("💡 過去の授業記録を呼び出して、内容を直接修正・上書き保存できます。")

    col1, col2 = st.columns(2)
    target_date = col1.date_input("📅 修正したい授業の日付", datetime.date.today())

    # 1. 指定された日付の記録を検索
    with st.spinner("記録を検索中..."):
        df_logs = robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

    if df_logs.empty or 'APIエラー発生' in df_logs.columns:
        st.warning("データが取得できませんでした。")
        return

    # 日付で絞り込み (文字列の前方一致)
    date_str = target_date.strftime("%Y/%m/%d")
    if '日時' in df_logs.columns:
        df_filtered = df_logs[df_logs['日時'].astype(str).str.contains(date_str, na=False)]
    else:
        st.error("スプレッドシートに「日時」列が見つかりません。")
        return

    if df_filtered.empty:
        st.warning(f"{date_str} の授業記録は見つかりませんでした。")
        return

    # 2. 該当する記録をプルダウンの選択肢にする
    options = []
    for idx, row in df_filtered.iterrows():
        opt_label = f"{row.get('名前', '不明')} - {row.get('科目', '不明')} ({row.get('授業コマ', '不明')})"
        options.append((idx, opt_label))

    selected_opt = col2.selectbox("📝 修正する記録を選択", options, format_func=lambda x: x[1])

    # 3. 選択された記録の編集フォームを表示
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
            new_adv = st.text_area("📖 授業進捗", value=str(record.get('進捗', '')))
            new_hw = st.text_area("🚀 次回の宿題範囲", value=str(record.get('次回の宿題範囲', '')))

            st.write("🧠 **授業中の様子・評価**")
            c_eval1, c_eval2 = st.columns(2)
            eval_opts = ["超集中", "前向き", "疲労気味", "ムラあり", "集中できない"]
            reac_opts = ["原因を分析した", "悔しがった", "放置しようとした"]
            
            current_conc = record.get('集中力', '前向き')
            current_reac = record.get('ミスへの反応', '原因を分析した')
            new_conc = c_eval1.selectbox("集中力", eval_opts, index=eval_opts.index(current_conc) if current_conc in eval_opts else 0)
            new_reac = c_eval2.selectbox("ミスへの反応", reac_opts, index=reac_opts.index(current_reac) if current_reac in reac_opts else 0)

            st.write("💬 **コメント事項**")
            # スプレッドシートの列名に合わせて取得
            new_advc = st.text_area("🗣️ 授業でのアドバイス", value=str(record.get('授業アドバイス', '')))
            new_pmsg = st.text_area("👪 保護者への連絡事項", value=str(record.get('保護者への連絡', '')))
            new_next_h = st.text_area("🔄 次回への引継ぎ事項", value=str(record.get('次回への引継ぎ', '')))

            submitted = st.form_submit_button("💾 修正を上書き保存する", type="primary", use_container_width=True)

            if submitted:
                with st.spinner("データを上書き保存中..."):
                    # 上書きするデータの辞書を作成
                    update_data = {
                        "出欠": new_att,
                        "科目": new_sub,
                        "遅刻時間": new_late,
                        "進捗": new_adv,
                        "次回の宿題範囲": new_hw,
                        "集中力": new_conc,
                        "ミスへの反応": new_reac,
                        "授業アドバイス": new_advc,
                        "保護者への連絡": new_pmsg,
                        "次回への引継ぎ": new_next_h
                    }
                    
                    success = robust_api_call(
                        update_lesson_record_in_sheet,
                        date_str=date_str,
                        student_name=record.get('生徒名'),
                        class_slot=record.get('授業コマ'),
                        new_data=update_data,
                        fallback_value=False
                    )

                    if success:
                        st.success("✅ 修正を上書き保存しました！")
                        st.cache_data.clear()
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 更新に失敗しました。対象のデータが見つからないか、通信エラーです。")