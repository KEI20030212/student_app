# views/textbook_manager.py

import streamlit as st
import pandas as pd
import io
import time
from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_textbook_master_raw,
    update_textbook_master_bulk
)

def cached_get_textbook_master_raw():
    return robust_api_call(get_textbook_master_raw, fallback_value=pd.DataFrame())

def render_textbook_manager_page():
    st.header("📚 テキスト情報一覧（マスタ管理）")
    st.write("登録されているテキストの章やページ範囲を確認・編集・一括追加できる管理画面です。")

    # 権限チェック（管理者のみ）
    user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'guest'))).lower()
    if user_role not in ['admin', 'sub_admin', 'owner', 'am', 'head_teacher']:
        st.error("このページは管理者のみアクセス可能です。")
        return

    # 🌟 NEW: アップローダーのリセット用キーを初期化（完了後に元の画面に戻すため）
    if "tb_uploader_key" not in st.session_state:
        st.session_state.tb_uploader_key = 0

    # データ取得（キャッシュを使うのでセルをいじってもサクサク！）
    with st.spinner("テキスト情報を読み込み中..."):
        df_master = cached_get_textbook_master_raw()

    if df_master.empty:
        st.warning("テキスト情報が取得できませんでした。スプレッドシートの設定を確認してください。")
        return

    # カラム名チェック
    req_cols = ["テキスト", "章", "単元名", "開始ページ", "終了ページ"]
    for col in req_cols:
        if col not in df_master.columns:
            if col == "単元名" and "章名" in df_master.columns:
                df_master.rename(columns={"章名": "単元名"}, inplace=True)
            else:
                st.error(f"スプレッドシートに必須列「{col}」が見つかりません。")
                return

    tab_view, tab_upload = st.tabs(["👁️ 一覧確認・直接編集", "📥 Excel/CSV 一括アップロード"])

    # ---------------------------------------------------------
    # タブ1: 一覧確認・直接編集
    # ---------------------------------------------------------
    with tab_view:
        st.write("👇 表のセルをクリックすると直接編集できます。編集後は「保存」ボタンを押してください。")
        
        # テキスト名で絞り込み機能
        text_names = ["すべて"] + list(df_master["テキスト"].dropna().unique())
        selected_text = st.selectbox("🔍 表示するテキストを絞り込む", text_names)
        
        if selected_text != "すべて":
            df_display = df_master[df_master["テキスト"] == selected_text].copy()
        else:
            df_display = df_master.copy()

        # データエディタ（直接編集可能な表）
        edited_df = st.data_editor(
            df_display[req_cols], 
            num_rows="dynamic", # 行の追加・削除も可能にする
            use_container_width=True,
            key="textbook_editor"
        )
        
        if st.button("💾 変更をスプレッドシートに保存", type="primary", use_container_width=True):
            with st.spinner("保存中..."):
                # もし絞り込んで編集した場合は、元のデータフレームに合成する
                if selected_text != "すべて":
                    df_new_full = df_master[df_master["テキスト"] != selected_text].copy()
                    df_final = pd.concat([df_new_full, edited_df], ignore_index=True)
                else:
                    df_final = edited_df
                
                success = robust_api_call(update_textbook_master_bulk, df_final[req_cols], fallback_value=False)
                if success:
                    st.success("✅ テキスト情報を更新しました！")
                    # 🌟 保存が成功したらキャッシュを消して最新のデータに更新する
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 更新に失敗しました。")

    # ---------------------------------------------------------
    # タブ2: 一括アップロード
    # ---------------------------------------------------------
    with tab_upload:
        st.write("ExcelやCSVファイルをアップロードして、テキスト情報を一括で大量に追加できます。")
        
        # フォーマットのダウンロードボタン
        st.markdown("#### 1. 入力用フォーマットのダウンロード")
        st.info("💡 まずはこちらのフォーマットをダウンロードし、データを入力してください。")
        
        # テンプレートデータの作成
        template_data = pd.DataFrame([
            {"テキスト": "新研究 数学", "章": "1", "単元名": "式の計算", "開始ページ": 10, "終了ページ": 20},
            {"テキスト": "新研究 数学", "章": "2", "単元名": "連立方程式", "開始ページ": 21, "終了ページ": 35},
            {"テキスト": "【説明】", "章": "数字のみ", "単元名": "単元の名前", "開始ページ": "数字のみ", "終了ページ": "数字のみ"},
            {"テキスト": "【説明】", "章": "一行目の列名を残し、それ以外はこの説明文を含め、全て削除してください"},
        ])
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            template_data.to_excel(writer, index=False, sheet_name='テキスト情報入力用')
            # 列幅調整
            writer.sheets['テキスト情報入力用'].set_column('A:A', 20)
            writer.sheets['テキスト情報入力用'].set_column('B:C', 15)
            writer.sheets['テキスト情報入力用'].set_column('D:E', 12)
            
        st.download_button(
            label="📥 入力用Excelフォーマットをダウンロード",
            data=excel_buffer.getvalue(),
            file_name="テキスト情報_入力用フォーマット.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        
        # アップロードエリア
        st.markdown("#### 2. データのアップロード")
        # 🌟 NEW: アップローダーのkeyにセッション変数を使い、完了後にリセットできるようにする
        uploaded_file = st.file_uploader(
            "完成したExcelまたはCSVファイルをアップロードしてください", 
            type=["xlsx", "csv"], 
            key=f"tb_uploader_{st.session_state.tb_uploader_key}"
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_uploaded = pd.read_csv(uploaded_file)
                else:
                    df_uploaded = pd.read_excel(uploaded_file)
                
                st.write("プレビュー (上から5件):")
                st.dataframe(df_uploaded.head(), use_container_width=True)
                
                # 列チェック
                missing_cols = [col for col in req_cols if col not in df_uploaded.columns]
                if missing_cols:
                    st.error(f"❌ 必須列が足りません: {', '.join(missing_cols)}")
                else:
                    # 説明行を消す（テキスト列が【説明】のもの）
                    df_upload_clean = df_uploaded[df_uploaded["テキスト"] != "【説明】"].copy()
                    
                    merge_mode = st.radio("アップロード方法を選択してください", 
                                          ["既存のデータに【追加】する", "既存のデータをすべて【上書き（入れ替え）】する"])
                    
                    if st.button("🚀 このデータで更新を実行する", type="primary", use_container_width=True):
                        # 🌟 NEW: プログレスバーの追加
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        status_text.text("データを結合・整形中...")
                        progress_bar.progress(20)
                        time.sleep(0.5)
                        
                        if merge_mode == "既存のデータに【追加】する":
                            df_final = pd.concat([df_master, df_upload_clean], ignore_index=True)
                        else:
                            df_final = df_upload_clean
                            
                        # 空行を消して整理
                        df_final = df_final.dropna(subset=["テキスト", "章"])
                        df_final = df_final[df_final["テキスト"].astype(str).str.strip() != ""]
                            
                        status_text.text("スプレッドシートへ送信中... (しばらくお待ちください)")
                        progress_bar.progress(60)
                        
                        # データ送信
                        success = robust_api_call(update_textbook_master_bulk, df_final[req_cols], fallback_value=False)
                        
                        if success:
                            progress_bar.progress(100)
                            status_text.text("更新完了！")
                            st.success("✅ 一括アップロードが完了しました！")
                            
                            # 🌟 NEW: アップローダーをリセットして元の画面に戻す
                            time.sleep(1.5)
                            st.session_state.tb_uploader_key += 1
                            st.rerun()
                        else:
                            progress_bar.empty()
                            status_text.empty()
                            st.error("❌ 更新に失敗しました。")
            except Exception as e:
                st.error(f"ファイルの読み込みエラー: {e}")