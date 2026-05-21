import streamlit as st
import json
import time
import base64
import io
from pypdf import PdfWriter
from utils.g_sheets import (
    get_quiz_maker_sheets,
    add_quiz_maker_sheet,
    delete_quiz_maker_sheet,
    get_gc_client
)

# 🌟 追加: 強化版APIコール関数をインポート
from utils.api_guard import robust_api_call

def render_word_quiz_maker_page():
    st.header("🔤 単語テスト作成・印刷")
    st.write("キクタン専用のレイアウトでPDFを瞬時に作成します。")

    # 🌟 強化: 既存のリスト取得機能を robust_api_call で保護
    quiz_dict = robust_api_call(get_quiz_maker_sheets, fallback_value={})

    # --- 新規登録機能（既存と同じ：必要に応じてキクタンを登録してください） ---
    with st.expander("➕ 新しい単語テストをリストに登録する"):
        with st.form("add_word_quiz_form"):
            new_name = st.text_input("📝 テスト名 (例: キクタン8問)")
            new_id = st.text_input("🔑 スプレッドシートID")
            new_full_marks = st.number_input("💯 満点", min_value=1, value=100)
            submit_new = st.form_submit_button("リストに登録する ✨")
            if submit_new and new_name:
                robust_api_call(add_quiz_maker_sheet, new_name, new_id.strip(), new_full_marks, "B5")
                st.success(f"「{new_name}」を登録しました！")
                time.sleep(1)
                st.rerun()

    # --- メイン設定 ---
    # 🌟 修正1：選択肢を「キクタン」の4つに限定
    target_options = ["キクタン8問", "キクタン16問", "キクタン32問", "キクタン50問", "WordCup20問", "WordCup100問", "WordCup200問"]
    
    # 登録されている中から、対象の4つだけを表示（登録がない場合は警告）
    available_options = [opt for opt in target_options if opt in quiz_dict]
    
    if not available_options:
        st.warning("⚠️ 「キクタン8問」〜「キクタン50問」がリストに登録されていません。上のプラスボタンから登録してください。")
        return

    quiz_name = st.selectbox("📚 ファイルを選択", available_options, key="word_quiz_select")
    quiz_data = quiz_dict[quiz_name]
    sheet_id = quiz_data.get("id", "") if isinstance(quiz_data, dict) else quiz_data

    # 🌟 修正2：問題数選択ラジオボタンを廃止し、背後で自動設定
    with st.container(border=True):
        st.markdown(f"#### ⚙️ 「{quiz_name}」の設定を適用中")
        
        portrait_val = "true"  # デフォルトは縦向き
        
        if quiz_name == "キクタン8問":
            ranges, p_size = ["A1:I18", "J1:R18"], "B5"
        elif quiz_name == "キクタン16問":
            ranges, p_size = ["A1:I18", "J1:R18"], "B5"
        elif quiz_name == "WordCup20問":
            ranges, p_size = ["A1:I23", "J1:R23"], "B5"    
        elif quiz_name == "キクタン32問":
            ranges, p_size = ["A1:J18", "M1:V18"], "A4"
        elif quiz_name == "WordCup100問":
            ranges, p_size = ["A1:AB27", "AC1:BD27"], "A3"
            portrait_val = "false"
        elif quiz_name == "WordCup200問":
            ranges, p_size = ["A1:AB27", "A29:AB55", "AC1:BD27", "AC29:BD55"], "A3"
            portrait_val = "false"  
        else: # キクタン50問
            ranges, p_size = ["A1:N27", "O1:AB27"], "A3"

        st.caption(f"自動設定：範囲 {ranges} / 用紙 {p_size}")

        # 範囲指定（ここは手動で調整が必要なため残しています）
        target_sheet_name = "確認テスト"
        c1, c2, c3 = st.columns(3)
        start_num = c1.number_input("はじめの番号", min_value=1, value=1, key="word_s")
        end_num = c2.number_input("おわりの番号", min_value=1, value=20, key="word_e")
        shuffle = c3.checkbox("🔀 シャッフルする", value=False, key="word_sh")

        if st.button(f"✨ {quiz_name} を作成する", type="primary", use_container_width=True):
            with st.spinner(f"{quiz_name} 生成中..."):
                try:
                    def update_sheet_and_get_gid():
                        gc = get_gc_client()
                        sh = gc.open_by_key(sheet_id)
                        
                        # 1. 範囲書き込み
                        setting_ws = sh.worksheet("テスト範囲指定")
                        setting_ws.update_acell('B2', start_num)
                        setting_ws.update_acell('B3', end_num)
                        setting_ws.update_acell('D3', shuffle) 
                        
                        # 2. シート取得
                        target_ws = sh.worksheet(target_sheet_name)
                        return target_ws.id

                    gid = robust_api_call(update_sheet_and_get_gid, fallback_value=None)
                    
                    if gid is None:
                        st.error("スプレッドシートの更新に失敗しました。")
                        st.stop()
                        
                    time.sleep(3) 

                    # PDF URL作成（ベース部分）
                    base_url = (
                        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
                        f"?format=pdf&gid={gid}&size={p_size}&portrait={portrait_val}"
                        f"&gridlines=false&scale=3&fitw=true"
                        f"&top_margin=0.2&bottom_margin=0.2&left_margin=0.2&right_margin=0.2"
                        f"&horizontal_alignment=CENTER&fzr=false&fzc=false"
                    )

                    # 4. ダウンロード＆結合処理
                    import requests
                    import google.auth.transport.requests
                    from google.oauth2.service_account import Credentials
                    
                    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
                    creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
                    creds.refresh(google.auth.transport.requests.Request())
                    headers = {"Authorization": f"Bearer {creds.token}"}
                    
                    merger = PdfWriter()
                    
                    # 🌟 魔法のループ処理：rangesに入っている範囲の数だけ自動で繰り返す！
                    for r in ranges:
                        # 範囲ごとにURLを作ってダウンロード
                        url = f"{base_url}&range={r}"
                        res = robust_api_call(requests.get, url, headers=headers, fallback_value=None)
                        
                        # もし失敗したらエラーを出してストップ
                        if res is None or res.status_code != 200:
                            st.error(f"PDFの取得に失敗しました。（範囲: {r}）")
                            st.stop()
                        
                        # 成功したらPDFの束に追加（結合）していく
                        merger.append(io.BytesIO(res.content))
                    
                    # 🌟 すべて結合し終わったらデータとして保存
                    merged_stream = io.BytesIO()
                    merger.write(merged_stream)
                    
                    st.session_state['word_pdf_merged'] = merged_stream.getvalue()
                    st.success("✅ 生成完了！")

                except Exception as e:
                    st.error(f"エラー: {e}")

    # --- ダウンロードUI ---
    if 'word_pdf_merged' in st.session_state:
        st.divider()
        b64_pdf = base64.b64encode(st.session_state['word_pdf_merged']).decode('utf-8')
        filename = f"{quiz_name}_テスト.pdf"
        st.markdown(f'<a href="data:application/pdf;base64,{b64_pdf}" download="{filename}" style="display: block; text-align: center; padding: 12px; background-color: #28a745; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-bottom: 10px;">📥 {filename} を開く</a>', unsafe_allow_html=True)