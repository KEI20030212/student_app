import streamlit as st
import pandas as pd
import time
from utils.g_sheets import (
    get_all_accounts, 
    add_new_account, 
    delete_account, 
    update_account_role,
    load_instructor_master,    # 🌟 追加：講師マスタの自動連動用
    update_instructor_master   # 🌟 追加：講師マスタの自動連動用
)

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
        account_list = []
        for uid, data in accounts_dict.items():
            raw_role = data.get("権限", "teacher")
            display_role = role_mapping.get(raw_role, f"❓ 不明 ({raw_role})")

            account_list.append({
                "ユーザーID": uid,
                "講師名": data.get("講師名", ""),
                "権限": display_role,
                "パスワード": "********" 
            })
        df_accounts = pd.DataFrame(account_list)
        st.dataframe(df_accounts, hide_index=True, use_container_width=True)
    else:
        st.info("アカウントデータがありません。（または通信エラー）")

    st.divider()

    # ==========================================
    # 1. 新規アカウント追加フォーム（全自動給与マスタ連動版）
    # ==========================================
    st.subheader("➕ 新規アカウントの作成")
    st.info("💡 アカウントを作成すると、給与ダッシュボードの「講師マスタ」にもデフォルト単価で自動的に初期設定が登録されます！")
    
    with st.form("create_account_form", clear_on_submit=True):
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
                index=4 
            )
            
        submit_btn = st.form_submit_button("✨ この内容でアカウントを作成する", use_container_width=True)
        
        if submit_btn:
            if not new_id or not new_pass or not new_name:
                st.error("⚠️ すべての項目を入力してください。")
            elif new_id in accounts_dict:
                st.error(f"⚠️ ユーザーID「{new_id}」は既に使われています。別のIDにしてください。")
            else:
                with st.spinner("アカウントと基本給マスタを同時生成中..."):
                    # 🌟 2つのシートへの登録をワンクリックで同時に行う強固なトランザクションロジック
                    def create_account_and_instructor_master():
                        # 1. アカウントの作成
                        acc_success = add_new_account(new_id, new_pass, new_name, new_role)
                        if not acc_success:
                            return False
                        
                        # 2. 講師マスタへの全自動基本給設定
                        df_instructors = load_instructor_master()
                        if df_instructors.empty or "講師名" not in df_instructors.columns:
                            df_instructors = pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])
                        
                        # 重複登録を防ぎつつ追記
                        if new_name.strip() not in df_instructors["講師名"].tolist():
                            new_row = pd.DataFrame([{"講師名": new_name.strip(), "1:1単価": 1875, "1:2単価": 1950, "1:3単価": 2100, "交通費": 0, "役職手当": 0}])
                            updated_df = pd.concat([df_instructors, new_row], ignore_index=True)
                            update_instructor_master(updated_df)
                        return True

                    success = robust_api_call(create_account_and_instructor_master, fallback_value=False)
                
                if success:
                    if 'all_accounts' in st.session_state:
                        del st.session_state['all_accounts']
                    st.cache_data.clear() # アプリ全体のキャッシュをクリアして確実に同期させる
                    time.sleep(1.5)
                    st.session_state['toast_msg'] = f"🎉 {new_name} 先生のアカウント作成 ＆ 給与マスタ初期設定が完了しました！"
                    st.rerun()
                else:
                    st.error("❌ アカウントの作成に失敗しました。通信状況を確認してください。")

    # ==========================================
    # 2. アカウント権限の変更
    # ==========================================
    st.divider()
    st.subheader("🔄 アカウント権限の変更")

    if accounts_dict:
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
                    if 'all_accounts' in st.session_state:
                        del st.session_state['all_accounts']
                    st.cache_data.clear()
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
        delete_options = [f"{uid} ({data.get('講師名', '名無し')})" for uid, data in accounts_dict.items()]
        
        with st.form("delete_account_form"):
            st.warning("⚠️ アカウントを削除すると、そのユーザーはログインできなくなります。この操作は元に戻せません。")
            selected_to_delete = st.selectbox("削除するアカウントを選択", options=delete_options)
            
            confirm_delete = st.checkbox("本当に削除してよろしいですか？")
            delete_btn = st.form_submit_button("🗑️ アカウントを削除する")
            
            if delete_btn:
                if not confirm_delete:
                    st.error("⚠️ 削除する場合は「本当に削除してよろしいですか？」にチェックを入れてください。")
                else:
                    target_id = selected_to_delete.split(" ")[0]
                    
                    if target_id == st.session_state.get('user_id'): 
                        st.error("⛔ 自分自身のアカウントは削除できません！")
                    else:
                        with st.spinner("アカウントを削除中..."):
                            success = robust_api_call(delete_account, target_id, fallback_value=False)
                        
                        if success:
                            if 'all_accounts' in st.session_state:
                                del st.session_state['all_accounts']
                            st.cache_data.clear()
                            time.sleep(1.5)
                            st.session_state['toast_msg'] = f"🗑️ アカウント「{target_id}」を削除しました。"
                            st.rerun()
                        else:
                            st.error("❌ アカウントの削除に失敗しました。")