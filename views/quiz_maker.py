import streamlit as st
import json
import streamlit.components.v1 as components
import time
import base64
import io
from pypdf import PdfWriter

# 裏方部隊から、スプレッドシートのURL（ID）を管理する関数などを呼び出します
from utils.g_sheets import (
    get_quiz_maker_sheets,
    add_quiz_maker_sheet,
    delete_quiz_maker_sheet,
    get_gc_client
)

def render_quiz_maker_page():
    st.header("🖨️ 小テスト作成・印刷")
    st.write("設定したスプレッドシートと連動して、自動で問題を抽出し、印刷用データを作成します。")

    quiz_dict = get_quiz_maker_sheets()

    with st.expander("➕ 新しい小テストをリストに登録する"):
        st.write("他の先生も使えるように、新しい小テストのファイルをリストに保存します！")
        with st.form("add_quiz_form"):
            new_name = st.text_input("📝 テストの名前 (例: 中2 数学 計算ドリル)")
            # 🌟 変更: IDの(必須)というプレッシャーをなくしました
            new_id = st.text_input("🔑 スプレッドシートのID (後から設定する場合は空欄でOK)", placeholder="1A2B3C4D5E6F7G...")
            new_full_marks = st.number_input("💯 満点", min_value=1, value=100)
            submit_new = st.form_submit_button("リストに登録する ✨")
            
            if submit_new:
                # 🌟 変更: 名前さえあれば登録できるようにしました
                if new_name:
                    save_id = new_id.strip() if new_id else ""
                    add_quiz_maker_sheet(new_name, save_id, new_full_marks)
                    st.success(f"「{new_name}」をリストに登録しました！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⚠️ テストの名前は必ず入力してください。")

    st.divider()

    if not quiz_dict:
        st.warning("小テストが登録されていません。上のメニューから登録してください。")
        return

    # リストを名前順に整列
    sorted_quiz_names = sorted(quiz_dict.keys())

    c_sel, c_del = st.columns([4, 1])
    with c_sel:
        quiz_name = st.selectbox("📚 使用する小テストのファイルを選択", sorted_quiz_names)
    
    with c_del:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        with st.popover("🗑️ 削除", use_container_width=True):
            st.warning(f"本当に「{quiz_name}」をリストから削除しますか？")
            if st.button("はい、削除します", type="primary", use_container_width=True):
                delete_quiz_maker_sheet(quiz_name)
                st.toast(f"🗑️ 「{quiz_name}」を削除しました！")
                time.sleep(1)
                st.rerun()

    # 選ばれた小テストのIDを取得
    # 選ばれた小テストのデータを取得
    quiz_data = quiz_dict[quiz_name]
    
    # もしデータが「IDと満点のセット（辞書）」だったら、IDだけを引っこ抜く
    if type(quiz_data) is dict:
        sheet_id = quiz_data["id"]
    else:
        # 古いデータで、文字だけが入っていた場合の保険
        sheet_id = quiz_data

    with st.container(border=True):
        st.markdown("#### ⚙️ 印刷設定")
        
        test_type = st.radio(
            "📝 テストの種類を選択", 
            ["確認テスト", "良問テスト(簡)", "良問テスト(難)"], 
            horizontal=True
        )
        
        if test_type == "確認テスト":
            target_sheet_name = "確認テスト"
            st.write("▼ 出題範囲を設定します")
            
            # 🌟 変更: 単一の章か、範囲指定かを選べるようにしました
            range_mode = st.radio("範囲の指定方法", ["1つの章から出題", "複数の章をまたいで出題"], horizontal=True)
            
            c1, c2, c3 = st.columns(3)
            
            if range_mode == "1つの章から出題":
                # 1つの章だけの場合は、入力項目を1つにして、裏でB2・B3に同じ数字を割り当てます
                target_num = c1.number_input("出題する章番号", min_value=1, value=1)
                start_num = target_num
                end_num = target_num
                shuffle = c2.checkbox("🔀 問題をシャッフルする", value=False)
            else:
                # 複数章の場合は今まで通り
                start_num = c1.number_input("はじめの番号 (B2セル)", min_value=1, value=1)
                end_num = c2.number_input("終わりの番号 (B3セル)", min_value=1, value=20)
                shuffle = c3.checkbox("🔀 問題をシャッフルする", value=False)
        else:
            c_chap, _ = st.columns([1, 2])
            chapter_num = c_chap.number_input("🔢 章番号 (〇に入る数字)", min_value=1, value=1, step=1)
            target_sheet_name = f"{test_type}{chapter_num}"
            st.info(f"💡 スプレッドシートの「{target_sheet_name}」シートをそのままPDF化します。")

        if st.button(f"✨ {target_sheet_name} を作成する", type="primary", use_container_width=True):
            # 🌟 変更: IDがない場合はここでストップして教える
            if not sheet_id:
                st.error("⚠️ このテストにはスプレッドシートのIDが登録されていません！一度削除してID付きで再登録をお願いします。")
            else:
                with st.spinner(f"魔法の小テストジェネレーターを起動中... [{target_sheet_name}]"):
                    try:
                        gc = get_gc_client()
                        sh = gc.open_by_key(sheet_id)
                        
                        if test_type == "確認テスト":
                            setting_ws = sh.worksheet("テスト範囲指定")
                            # 🌟 変更: start_num と end_num が単一章なら同じ数字で飛んでいきます
                            setting_ws.update_acell('B2', start_num)
                            setting_ws.update_acell('B3', end_num)
                            setting_ws.update_acell('D3', shuffle) 
                            time.sleep(3) 
                        
                        target_ws = None
                        for ws in sh.worksheets():
                            clean_ws_title = ws.title.replace(" ", "").replace("　", "")
                            clean_target = target_sheet_name.replace(" ", "").replace("　", "")
                            
                            if clean_ws_title == clean_target:
                                target_ws = ws
                                break
                                
                        if target_ws is None:
                            existing_sheets = [ws.title for ws in sh.worksheets()]
                            st.error(f"❌ 「{target_sheet_name}」という名前のシートが見つかりません！")
                            st.info(f"🔍 【プログラムが見つけた実際のシート名一覧】\n" + " ／ ".join(existing_sheets))
                            st.write("💡 アドバイス: カッコの全角・半角（ `()` と `（）` ）がスプレッドシートと合っているか確認してください！")
                            st.stop()
                            
                        gid = target_ws.id
                        
                        base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=pdf&gid={gid}&portrait=true&size=A4&gridlines=false&fitw=true"
                        url_q = f"{base_url}&range=A1:I28"
                        url_a = f"{base_url}&range=J1:R28"
                        
                        import google.auth.transport.requests
                        import requests
                        from google.oauth2.service_account import Credentials
                        
                        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                        secret_dict = json.loads(st.secrets["gcp_service_account_json"])
                        creds = Credentials.from_service_account_info(secret_dict, scopes=scopes)
                        req = google.auth.transport.requests.Request()
                        creds.refresh(req)
                        headers = {"Authorization": f"Bearer {creds.token}"}
                        
                        res_q = requests.get(url_q, headers=headers)
                        res_a = requests.get(url_a, headers=headers)
                        
                        merger = PdfWriter()
                        merger.append(io.BytesIO(res_q.content))
                        merger.append(io.BytesIO(res_a.content))
                        
                        merged_pdf_stream = io.BytesIO()
                        merger.write(merged_pdf_stream)
                        
                        st.session_state['pdf_q'] = res_q.content
                        st.session_state['pdf_a'] = res_a.content
                        st.session_state['pdf_merged'] = merged_pdf_stream.getvalue()
                        st.session_state['generated_test_name'] = target_sheet_name 
                        
                        st.success(f"✅ 【{target_sheet_name}】のセットPDF生成が完了しました！")
                    except Exception as e:
                        # 🌟 どこでエラーが起きたかもう少し詳しく表示するように変更
                        st.error(f"❌ エラーが発生しました。")
                        st.warning(f"詳細メッセージ: {e}")
                        if 'sheet_id' in locals():
                            st.info(f"使用しようとしたID: {sheet_id}")
                        if 'target_sheet_name' in locals():
                            st.info(f"探そうとしたシート名: {target_sheet_name}")
    # ==========================================
    # ダウンロードUI
    # ==========================================
    if 'pdf_merged' in st.session_state:
        st.divider()
        st.subheader("👀 ダウンロード ＆ 印刷 (PDF)")

        def display_pdf(pdf_bytes, filename, color="#FF4B4B"):
            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            html_button = f'''
            <a href="data:application/pdf;base64,{b64_pdf}" download="{filename}" target="_blank" 
               style="display: block; text-align: center; padding: 12px; background-color: {color}; 
                      color: white; text-decoration: none; border-radius: 8px; font-weight: bold; 
                      margin-bottom: 10px; transition: 0.3s;">
                📥 【 {filename} 】を開く / 印刷する
            </a>
            '''
            st.markdown(html_button, unsafe_allow_html=True)

        gen_name = st.session_state.get('generated_test_name', 'テスト')

        st.markdown("#### 📚 セット印刷（おすすめ！）")
        st.info("💡 1ページ目が問題、2ページ目が解答になっています。これ1つを両面印刷または2ページ印刷すれば完了です！")
        display_pdf(st.session_state['pdf_merged'], f"{quiz_name}_{gen_name}_問題解答セット.pdf", color="#28a745") 

        st.markdown("<br>#### 📄 個別データ（必要な場合のみ）", unsafe_allow_html=True)
        tab_q, tab_a = st.tabs(["📝 問題のみ", "💡 解答のみ"])
        with tab_q: display_pdf(st.session_state['pdf_q'], f"{quiz_name}_{gen_name}_問題のみ.pdf")
        with tab_a: display_pdf(st.session_state['pdf_a'], f"{quiz_name}_{gen_name}_解答のみ.pdf")