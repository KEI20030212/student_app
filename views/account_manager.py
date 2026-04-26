# views/account_manager.py

import streamlit as st
import pandas as pd
from utils.g_sheets import get_all_accounts, add_new_account, delete_account

def render_account_manager_page():
    # 念のための最強のセキュリティロック（URL等で直接アクセスされた時用）
    if st.session_state.get('role') != 'admin':
        st.error("⛔ このページは教室長（管理者）専用です。")
        return
    if 'toast_msg' in st.session_state:
        st.toast(st.session_state['toast_msg'], icon="✨")
        del st.session_state['toast_msg']

    st.header("⚙️ アカウント・システム設定")
    
    # 1. 現在のアカウント一覧を取得
    accounts_dict = get_all_accounts()
    
    st.subheader("👥 登録済みアカウント一覧")
    if accounts_dict:
        role_mapping = {
            "owner": "👑 オーナー",
            "admin": "🏢 教室長",
            "am": "👔 AM",
            "head_teacher": "🎓 主任講師",
            "teacher": "👩‍🏫 講師"
        }
        # 辞書型をデータフレームに変換して見やすくする
        account_list = []
        for uid, data in accounts_dict.items():
            raw_role = data.get("権限", "teacher") # 権限がない場合はとりあえずteacher扱い
            display_role = role_mapping.get(raw_role, f"❓ 不明 ({raw_role})")

            account_list.append({
                "ユーザーID": uid,
                "講師名": data.get("講師名", ""),
                "権限": display_role,
                "パスワード": "********" # 👈 セキュリティのため隠す！
            })
        df_accounts = pd.DataFrame(account_list)
        st.dataframe(df_accounts, hide_index=True, use_container_width=True)
    else:
        st.info("アカウントデータがありません。")

    st.divider()

    # 2. 新規アカウント追加フォーム
    st.subheader("➕ 新規アカウントの作成")
    st.info("💡 【重要】「講師名」は、給与ダッシュボードで設定した名前と一言一句同じにしてください。（スペースの有無などに注意）")
    
    with st.form("create_account_form", clear_on_submit=True): # 送信後にフォームを空にする
        col1, col2 = st.columns(2)
        with col1:
            new_id = st.text_input("👤 ユーザーID (半角英数字)")
            new_name = st.text_input("🏷️ 講師名 (例: 田中 太郎)")
        with col2:
            new_pass = st.text_input("🔑 初期パスワード", type="password")
            role_mapping = {
                "owner": "👑 オーナー",
                "admin": "🏢 教室長",
                "am": "👔 AM",
                "head_teacher": "🎓 主任講師",
                "teacher": "👩‍🏫 講師"
            }
            new_role = st.selectbox(
                "🛡️ 権限", 
                options=["owner", "admin", "am", "head_teacher", "teacher"], 
                format_func=lambda x: role_mapping[x]
            )
            
        submit_btn = st.form_submit_button("✨ この内容でアカウントを作成する", use_container_width=True)
        
        if submit_btn:
            # 入力漏れチェック
            if not new_id or not new_pass or not new_name:
                st.error("⚠️ すべての項目を入力してください。")
            elif new_id in accounts_dict:
                st.error(f"⚠️ ユーザーID「{new_id}」は既に使われています。別のIDにしてください。")
            else:
                # 登録処理を実行
                with st.spinner("スプレッドシートに登録中..."):
                    success = add_new_account(new_id, new_pass, new_name, new_role)
                
                if success:
                    get_all_accounts.clear()
                    # 成功メッセージを表示（toastは画面右下にフワッと出ます）
                    st.session_state['toast_msg'] = f"✅ {new_name} 先生のアカウントを作成しました！"
                    
                    # 画面を再起動して最新のリストを再読み込み
                    st.rerun()
    # ==========================================
    # 🌟 3. 新規追加: アカウント削除機能
    # ==========================================
    st.divider()
    st.subheader("🗑️ アカウントの削除")
    
    if accounts_dict:
        # 削除用の選択肢を作成（例: "user01 (田中 太郎)"）
        delete_options = [f"{uid} ({data.get('講師名', '名無し')})" for uid, data in accounts_dict.items()]
        
        with st.form("delete_account_form"):
            st.warning("⚠️ アカウントを削除すると、そのユーザーはログインできなくなります。この操作は元に戻せません。")
            selected_to_delete = st.selectbox("削除するアカウントを選択", options=delete_options)
            
            # 間違えて消さないようにチェックボックスでワンクッション置く
            confirm_delete = st.checkbox("本当に削除してよろしいですか？")
            
            delete_btn = st.form_submit_button("🗑️ アカウントを削除する", type="primary")
            
            if delete_btn:
                if not confirm_delete:
                    st.error("⚠️ 削除する場合は「本当に削除してよろしいですか？」にチェックを入れてください。")
                else:
                    # 選択肢の文字列 "user01 (田中 太郎)" から、ユーザーID "user01" だけを抽出
                    target_id = selected_to_delete.split(" ")[0]
                    
                    # ログイン中の自分自身のアカウントは消せないようにする（事故防止）
                    # （※ログインIDのセッション名が 'username' ではない場合は適宜直してください）
                    if target_id == st.session_state.get('username'): 
                        st.error("⛔ 自分自身のアカウントは削除できません！")
                    else:
                        with st.spinner("アカウントを削除中..."):
                            success = delete_account(target_id)
                        
                        if success:
                            get_all_accounts.clear()

                            st.session_state['toast_msg'] = f"🗑️ アカウント「{target_id}」を削除しました。"
                            st.rerun()
                        else:
                            st.error("❌ アカウントの削除に失敗しました。")