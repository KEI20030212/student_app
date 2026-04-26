import streamlit as st
from utils.g_sheets import get_all_accounts, save_message, get_sent_messages

def render_message_sender_page():
    st.header("💌 メッセージ送信")

    tab1, tab2 = st.tabs(["✏️ メッセージを送る", "🕰️ 送信履歴を見る"])

    raw_accounts = get_all_accounts()
    safe_accounts = {str(k).strip().lower(): v for k, v in raw_accounts.items()}

    # ==========================================
    # タブ1：送信フォーム
    # ==========================================
    with tab1:
        st.markdown("他の先生や教室長にダイレクトメッセージを送ることができます。")
        
        user_options = {}
        for target_id, info in safe_accounts.items():
            name = info.get("講師名", "不明")
            role = str(info.get("権限", "")).strip().lower()
            
            if role == "admin":
                suffix = "教室長"
            elif role == "owner":
                suffix = "社長"
            elif role == "head_teacher":
                suffix = "主任講師"
            else:
                suffix = "先生"
            
            user_options[f"{name} {suffix} (ID: {target_id})"] = target_id

        with st.container(border=True):
            with st.form("send_message_form", clear_on_submit=True):
                selected_label = st.selectbox("👤 宛先を選択", options=list(user_options.keys()))
                message_body = st.text_area("💬 メッセージ内容", height=150, placeholder="お疲れ様です。明日の授業についてですが...")
                submit = st.form_submit_button("メッセージを送信する 🚀", use_container_width=True)
                
                if submit:
                    if not message_body.strip():
                        st.error("⚠️ メッセージを入力してください。")
                    else:
                        receiver_id = user_options[selected_label]
                        sender_id = str(st.session_state.get('user_id', 'unknown')).strip()
                        
                        with st.spinner("送信中..."):
                            success = save_message(sender_id, receiver_id, message_body)
                        if success:
                            st.success(f"✅ {selected_label} 宛にメッセージを送信しました！")

    # ==========================================
    # タブ2：送信履歴の表示
    # ==========================================
    with tab2:
        st.markdown("あなたがこれまでに送信したメッセージの履歴です。")
        
        my_user_id = str(st.session_state.get('user_id', '')).strip().lower()
        if my_user_id:
            sent_msgs = get_sent_messages(my_user_id)
            
            if not sent_msgs:
                st.info("まだ送信したメッセージはありません。")
            else:
                unread_msgs = [m for m in sent_msgs if m.get("状態", "未読") in ["未読", "False"]]
                read_msgs = [m for m in sent_msgs if m not in unread_msgs]

                # ----------------------------------------
                # 📩 相手が未読のメッセージ枠
                # ----------------------------------------
                if unread_msgs:
                    st.markdown("##### 📩 相手がまだ読んでいないメッセージ (未読)")
                    for msg in unread_msgs:
                        date_str = msg.get("送信日時", "")
                        raw_receiver_id = msg.get("受信者ID", "")
                        text = msg.get("メッセージ内容", "")
                        
                        receiver_id = str(raw_receiver_id).strip().lower()
                        account_info = safe_accounts.get(receiver_id, {})
                        base_name = account_info.get("講師名")
                        role = str(account_info.get("権限", "")).strip().lower()

                        if receiver_id == "admin": receiver_name = "教室長"
                        elif receiver_id == "owner": receiver_name = "社長"
                        elif receiver_id == "head_teacher": receiver_name = "主任講師"
                        elif base_name:
                            if role == "admin": receiver_name = f"{base_name} 教室長"
                            elif role == "owner": receiver_name = f"{base_name} 社長"
                            elif role == "head_teacher": receiver_name = f"{base_name} 主任講師"
                            else: receiver_name = f"{base_name} 先生"
                        else: receiver_name = f"ID:{raw_receiver_id} (名前未設定)"
                        
                        with st.chat_message("assistant"):
                            st.markdown(f"**{receiver_name} 宛て** 🕒 {date_str} / **📩 未読**")
                            formatted_text = text.replace('\n', '  \n')
                            st.write(formatted_text)

                # ----------------------------------------
                # ✅ 相手が確認済みのメッセージ枠（検索機能つき！）
                # ----------------------------------------
                if read_msgs:
                    is_expanded = len(unread_msgs) == 0
                    
                    with st.expander("✅ 相手が確認済みのメッセージ (既読) を見る", expanded=is_expanded):
                        
                        # 🌟 検索ボックスを追加
                        search_query = st.text_input("🔍 メッセージを検索", placeholder="宛先の名前や、メッセージのキーワードを入力...")
                        
                        with st.container(height=300):
                            found_count = 0 # 検索にヒットした件数をカウント
                            
                            for msg in read_msgs:
                                date_str = msg.get("送信日時", "")
                                raw_receiver_id = msg.get("受信者ID", "")
                                text = msg.get("メッセージ内容", "")
                                
                                receiver_id = str(raw_receiver_id).strip().lower()
                                account_info = safe_accounts.get(receiver_id, {})
                                base_name = account_info.get("講師名")
                                role = str(account_info.get("権限", "")).strip().lower()

                                if receiver_id == "admin": receiver_name = "教室長"
                                elif receiver_id == "owner": receiver_name = "社長"
                                elif receiver_id == "head_teacher": receiver_name = "主任講師"
                                elif base_name:
                                    if role == "admin": receiver_name = f"{base_name} 教室長"
                                    elif role == "owner": receiver_name = f"{base_name} 社長"
                                    elif role == "head_teacher": receiver_name = f"{base_name} 主任講師"
                                    else: receiver_name = f"{base_name} 先生"
                                else: receiver_name = f"ID:{raw_receiver_id} (名前未設定)"
                                
                                # 🌟 検索キーワードでの絞り込み処理
                                if search_query:
                                    # 宛先名かメッセージ内容のどちらかにキーワードが含まれていれば表示（大文字小文字を区別しない）
                                    if search_query.lower() not in text.lower() and search_query.lower() not in receiver_name.lower():
                                        continue # 一致しない場合はスキップして次のメッセージへ
                                
                                found_count += 1
                                
                                with st.chat_message("user"):
                                    st.markdown(f"**{receiver_name} 宛て** 🕒 {date_str} / **✅ 既読**")
                                    formatted_text = text.replace('\n', '  \n')
                                    st.write(formatted_text)
                            
                            # 検索した結果、1件も見つからなかった場合の表示
                            if search_query and found_count == 0:
                                st.info(f"「{search_query}」を含むメッセージは見つかりませんでした。")