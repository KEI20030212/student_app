import streamlit as st
import pandas as pd
import time
from utils.g_sheets import get_all_accounts, add_new_account, delete_account, update_account_role

# 🌟 追加: アカウント管理画面もAPIガードで鉄壁に守る！
from utils.api_guard import robust_api_call

def render_account_manager_page():
    allowed_roles = ['admin', 'owner', 'am']
    if st.session_state.get('role') not in allowed_roles:
        st.error("⛔ このページは管理者専用です。")
        return
    if 'toast_msg' in st.session_state:
        st.toast(st.session_state['toast_msg'], icon="✨")
        del st.session_state['toast_msg']

    st.header("⚙️ アカウント・システム設定")
    
    with st.spinner("アカウント情報を取得中..."):
        accounts_dict = robust_api_call(get_all_accounts, force_refresh=True, fallback_value={})
    
    role_mapping = {
        "owner": "👑 オーナー",
        "admin": "🏢 教室長",
        "am": "👔 AM",
        "head_teacher": "🎓 主任講師",
        "teacher": "👩‍🏫 講師"
    }

    st.subheader("👥 登録済みアカウント一覧")
    if accounts_dict:
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
        st.info("アカウントデータがありません。（または通信エラー）")

    st.divider()

    # ==========================================
    # 1. 新規アカウント追加フォーム
    # ==========================================
    st.subheader("➕ 新規アカウントの作成")
    st.info("💡 【重要】「講師名」は、給与ダッシュボードで設定した名前と一言一句同じにしてください。（スペースの有無などに注意）")
    
    with st.form("create_account_form", clear_on_submit=True): # 送信後にフォームを空にする
        col1, col2 = st.columns(2)
        with col1:
            new_id = st.text_input("👤 ユーザーID (半角英数字)")
            new_name = st.text_input("🏷️ 講師名 (例: 田中 太郎)")
        with col2:
            new_pass = st.text_input("🔑 初期パスワード", type="password")
            new_role = st.selectbox(
                "🛡️ 権限", 
                options=["owner", "admin", "am", "head_teacher", "teacher"], 
                format_func=lambda x: role_mapping[x],
                index=4 # デフォルトを「講師」にする
            )
            
        submit_btn = st.form_submit_button("✨ この内容でアカウントを作成する", use_container_width=True)
        
        if submit_btn:
            # 入力漏れチェック
            if not new_id or not new_pass or not new_name:
                st.error("⚠️ すべての項目を入力してください。")
            elif new_id in accounts_dict:
                st.error(f"⚠️ ユーザーID「{new_id}」は既に使われています。別のIDにしてください。")
            else:
                with st.spinner("スプレッドシートに登録中..."):
                    success = robust_api_call(add_new_account, new_id, new_pass, new_name, new_role, fallback_value=False)
                
                if success:
                    if 'all_accounts' in st.session_state:
                        del st.session_state['all_accounts']
                    time.sleep(1.5)
                    st.session_state['toast_msg'] = f"✅ {new_name} 先生のアカウントを作成しました！"
                    st.rerun()
                else:
                    st.error("❌ アカウントの作成に失敗しました。通信状況を確認してください。")

    # ==========================================
    # 🌟 2. 新規追加: アカウント権限の変更
    # ==========================================
    st.divider()
    st.subheader("🔄 アカウント権限の変更")

    if accounts_dict:
        # 現在の権限も表示して分かりやすくする (例: "user01 (田中 太郎) - 現在: 👩‍🏫 講師")
        edit_options = [f"{uid} ({data.get('講師名', '名無し')}) - 現在: {role_mapping.get(data.get('権限', 'teacher'), '不明')}" for uid, data in accounts_dict.items()]

        with st.form("edit_role_form"):
            selected_to_edit = st.selectbox("権限を変更するアカウントを選択", options=edit_options)
            
            update_role = st.selectbox(
                "🛡️ 新しい権限", 
                options=["owner", "admin", "am", "head_teacher", "teacher"], 
                format_func=lambda x: role_mapping[x]
            )

            update_btn = st.form_submit_button("🔄 このアカウントの権限を更新する", type="primary")

            if update_btn:
                target_id = selected_to_edit.split(" ")[0]

                with st.spinner("権限を更新中..."):
                    success = robust_api_call(update_account_role, target_id, update_role, fallback_value=False)
                
                if success:
                    # 🌟 1. 記憶を正しく消去する
                    if 'all_accounts' in st.session_state:
                        del st.session_state['all_accounts']
                        
                    time.sleep(1.5)
                    
                    st.session_state['toast_msg'] = f"🔄 アカウント「{target_id}」の権限を【 {role_mapping[update_role]} 】に変更しました。"
                    st.rerun()
                else:
                    st.error("❌ 権限の更新に失敗しました。")
                    
    # ==========================================
    # 3. アカウント削除機能
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
            
            delete_btn = st.form_submit_button("🗑️ アカウントを削除する") # 削除ボタンの色を通常にする(誤爆防止)
            
            if delete_btn:
                if not confirm_delete:
                    st.error("⚠️ 削除する場合は「本当に削除してよろしいですか？」にチェックを入れてください。")
                else:
                    # 選択肢の文字列 "user01 (田中 太郎)" から、ユーザーID "user01" だけを抽出
                    target_id = selected_to_delete.split(" ")[0]
                    
                    # ログイン中の自分自身のアカウントは消せないようにする（事故防止）
                    if target_id == st.session_state.get('user_id'): 
                        st.error("⛔ 自分自身のアカウントは削除できません！")
                    else:
                        with st.spinner("アカウントを削除中..."):
                            success = robust_api_call(delete_account, target_id, fallback_value=False)
                        
                        if success:
                            if 'all_accounts' in st.session_state:
                                del st.session_state['all_accounts']
                            time.sleep(1.5)
                            st.session_state['toast_msg'] = f"🗑️ アカウント「{target_id}」を削除しました。"
                            st.rerun()
                        else:
                            st.error("❌ アカウントの削除に失敗しました。")