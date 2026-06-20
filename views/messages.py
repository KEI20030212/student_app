import streamlit as st
from utils.g_sheets import (
    get_my_messages,
    get_all_accounts,
    mark_messages_as_read
)
from utils.api_guard import robust_api_call

def render_messages_page():
    st.header("💌 あなた宛てのメッセージ")
    
    my_user_id = st.session_state.get('user_id')
    
    if my_user_id:
        messages = robust_api_call(lambda: get_my_messages(my_user_id), fallback_value=[])
        
        if not messages or (isinstance(messages, dict) and "APIエラー発生" in messages):
            st.info("現在、新しいメッセージはありません。")
        else:
            unread_msgs = [m for m in messages if m.get("状態", "未読") in ["未読", "False"]]
            read_msgs = [m for m in messages if m not in unread_msgs]
            
            if unread_msgs:
                robust_api_call(lambda: mark_messages_as_read(my_user_id), fallback_value=False)
                get_my_messages.clear()
            
            raw_accounts = robust_api_call(get_all_accounts, fallback_value={})
            safe_accounts = {str(k).strip().lower(): v for k, v in raw_accounts.items()} if raw_accounts else {}
            
            # 📩 新着メッセージ枠
            if unread_msgs:
                st.markdown("##### 📩 新着メッセージ")
                for msg in unread_msgs:
                    sender_name = "送信者不明"
                    sender_id_clean = str(msg.get("送信者ID", "")).strip().lower()
                    account_info = safe_accounts.get(sender_id_clean, {})
                    base_name = account_info.get("講師名")
                    if base_name: sender_name = f"{base_name} 先生"
                    
                    with st.chat_message("assistant"):
                        st.markdown(f"**{sender_name}** から 🕒 {msg.get('送信日時', '')} 🔴 **New!**")
                        st.write(msg.get("メッセージ内容", "").replace('\n', '  \n'))
            
            # ✅ 過去のメッセージ枠
            if read_msgs:
                with st.expander("✅ 過去のメッセージを表示"):
                    for msg in read_msgs:
                        with st.chat_message("user"):
                            st.write(msg.get("メッセージ内容", "").replace('\n', '  \n'))
    else:
        st.warning("⚠️ ユーザー情報が取得できません。再ログインしてください。")