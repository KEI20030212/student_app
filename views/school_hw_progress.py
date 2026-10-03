import streamlit as st
import pandas as pd
import io

def group_consecutive_pages(pages):
    """[10, 11, 12, 15] を 'P.10〜12、P.15' のように見やすくまとめる関数"""
    if not pages: return ""
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append(f"P.{start}" if start == prev else f"P.{start}〜{prev}")
            start = prev = p
    ranges.append(f"P.{start}" if start == prev else f"P.{start}〜{prev}")
    return "、".join(ranges)

def render_hw_progress(df_sw_logs, master_dict):
    st.write("日々の授業で入力された「ページ数」から、テキストごとの進捗を自動計算しています！")
    
    if df_sw_logs.empty:
        st.info("学校ワークの進捗ログがまだありません。")
        return
        
    if not master_dict:
        st.warning("「テキスト情報一覧」から章とページの設定を取得できませんでした。スプレッドシートをご確認ください。")
        return

    with st.spinner("ページごとの周回数を自動計算中...🚀"):
        # ==========================================
        # 🧠 計算ロジック：1ページ単位でクリア回数をカウント
        # ==========================================
        page_counts = {}
        for _, row in df_sw_logs.iterrows():
            s_name = str(row.get('生徒名', '')).strip()
            t_name = str(row.get('テキスト名', '')).strip()
            try:
                start_p = int(float(row.get('開始P', 0)))
                end_p = int(float(row.get('終了P', 0)))
            except:
                continue
                
            if start_p == 0 and end_p == 0: continue
                
            if s_name not in page_counts: page_counts[s_name] = {}
            if t_name not in page_counts[s_name]: page_counts[s_name][t_name] = {}
                
            for p in range(start_p, end_p + 1):
                page_counts[s_name][t_name][p] = page_counts[s_name][t_name].get(p, 0) + 1

        results = {}
        alerts = []
        
        for t_name, chapters in master_dict.items():
            target_students = [s for s, t_dict in page_counts.items() if t_name in t_dict]
            if not target_students: continue
                
            matrix_data = []
            for s_name in target_students:
                row_data = {"生徒名": s_name}
                student_pages = page_counts[s_name][t_name]
                # 生徒がそのテキストで進めた最大のページ番号
                max_done_page = max(student_pages.keys()) if student_pages else 0
                
                total_chap = len(chapters)
                completed_chap = 0
                
                for chap_info in chapters:
                    c_name = chap_info["chapter"]
                    c_start = chap_info["start"]
                    c_end = chap_info["end"]
                    
                    # その章の全ページのクリア回数リストを取得
                    counts = [student_pages.get(p, 0) for p in range(c_start, c_end + 1)]
                    if not counts:
                        row_data[c_name] = "✖"
                        continue
                        
                    min_c = min(counts) # 章の中で一番やっていないページの回数
                    max_c = max(counts) # 章の中で一番やっているページの回数
                    
                    # 🌟 判定ロジック
                    if min_c >= 3: mark = "👑"
                    elif min_c == 2: mark = "◎"
                    elif min_c == 1: mark = "〇"
                    elif max_c > 0: mark = "△"
                    else: mark = "✖"
                    
                    row_data[c_name] = mark
                    if min_c >= 1: completed_chap += 1
                    
                    # 🚨 アラート判定: この章が完了しておらず、かつ、これより先のページをやっている場合
                    if mark in ["△", "✖"] and max_done_page > c_end:
                        missing_pages = [p for p in range(c_start, c_end + 1) if student_pages.get(p, 0) == 0]
                        if missing_pages:
                            alerts.append({
                                "生徒名": s_name,
                                "テキスト名": t_name,
                                "章": c_name,
                                "飛ばしているページ": group_consecutive_pages(missing_pages)
                            })
                            
                # 進捗率を追加
                row_data["進捗率"] = f"{int((completed_chap / total_chap) * 100)}%" if total_chap > 0 else "0%"
                matrix_data.append(row_data)
                
            df_matrix = pd.DataFrame(matrix_data)
            results[t_name] = df_matrix

    # ==========================================
    # 🚨 アラートの表示
    # ==========================================
    if alerts:
        with st.expander("🚨 ページ飛ばしアラート（要確認！）", expanded=True):
            st.error("以下の生徒は、先のページに進んでいるにも関わらず、途中のページが未実施になっています。")
            df_alerts = pd.DataFrame(alerts)
            st.dataframe(df_alerts, use_container_width=True)
    else:
        st.success("✨ 現在、不自然なページ飛ばしが発生している生徒はいません。")

    st.divider()

    # ==========================================
    # 📊 マトリックス表の表示とExcel出力
    # ==========================================
    if not results:
        st.info("テキストの進捗データが計算できませんでした。")
        return
        
    selected_text = st.selectbox("📊 進捗を表示するテキストを選択", list(results.keys()))
    
    if selected_text:
        df_show = results[selected_text]
        
        # 背景色の設定
        def style_matrix(val):
            if val == "👑": return "background-color: #fffacd; color: #000; font-weight: bold;"
            if val == "◎": return "background-color: #c6efce; color: #006100;"
            if val == "〇": return "background-color: #e2efda; color: #385723;"
            if val == "△": return "background-color: #fff2cc; color: #d6961c;"
            if val == "✖": return "color: #ccc;"
            return ""
            
        try:
            styled_df = df_show.style.applymap(style_matrix, subset=df_show.columns.drop(["生徒名", "進捗率"]))
        except AttributeError:
            styled_df = df_show.style.map(style_matrix, subset=df_show.columns.drop(["生徒名", "進捗率"]))
            
        st.dataframe(styled_df, use_container_width=True)
        
        # Excelダウンロード用バッファ
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            styled_df.to_excel(writer, sheet_name="進捗マトリックス", index=False)
            
        st.download_button(
            label=f"📥 【{selected_text}】の進捗表をExcelでダウンロード",
            data=excel_buffer.getvalue(),
            file_name=f"{selected_text}_進捗マトリックス.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )