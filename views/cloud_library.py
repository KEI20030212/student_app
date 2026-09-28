import streamlit as st
import pandas as pd
import time
import os
from utils.g_sheets import get_quiz_master_dict
from utils.g_drive import (
    upload_library_file, 
    list_library_files,
    list_library_folders
)
from utils.api_guard import robust_api_call

CAT_QUIZ = "小テスト・確認テスト"
CAT_EXAM = "定期テスト過去問"

def render_cloud_library_page():
    st.header("📚 教材クラウド書庫")
    st.write("塾の公式プリント（小テスト、過去問など）を1秒で検索・ダウンロードできる共有書庫です。")
    
    user_role = str(st.session_state.get('role', st.session_state.get('user_role', 'guest'))).lower()
    is_admin = user_role in ['admin', 'owner', 'am']
    
    with st.spinner("書庫のインデックスを読み込み中..."):
        quiz_details = robust_api_call(get_quiz_master_dict, fallback_value={})
        quiz_names = []
        for key in quiz_details.keys():
            if "_" in key:
                q_name = key.split("_", 1)[0]
                if q_name not in quiz_names:
                    quiz_names.append(q_name)
                    
        school_names = [
            "田端中学校", "東十条中学校", "北中学校", "南中学校", "第一中学校", "第二中学校", "その他"
        ]

    st.divider()

    # ==========================================
    # 🌟 閲覧・ダウンロードエリア
    # ==========================================
    tab_quiz, tab_exam = st.tabs([f"📝 {CAT_QUIZ}", f"🏫 {CAT_EXAM}"])
    
    with tab_quiz:
        st.subheader("📝 小テスト・確認テストを探す")
        if not quiz_names:
            st.warning("設定シートから小テスト名が取得できません。")
        else:
            selected_quiz = st.selectbox("📚 テキスト・テスト名を選択", ["-- 選択してください --"] + quiz_names, key="sel_q_txt")
            
            if selected_quiz != "-- 選択してください --":
                with st.spinner("単元・章のフォルダを探しています..."):
                    chapter_folders = robust_api_call(list_library_folders, CAT_QUIZ, selected_quiz, fallback_value=[])
                
                selected_chapter = None
                if chapter_folders:
                    selected_chapter = st.selectbox("📖 単元・章を選択", ["-- 選択してください --", "-- 直下のファイル --"] + chapter_folders, key="sel_q_chap")
                
                if not chapter_folders or (chapter_folders and selected_chapter and selected_chapter != "-- 選択してください --"):
                    with st.spinner("書庫からPDFを探しています...🔍"):
                        files = robust_api_call(list_library_files, CAT_QUIZ, selected_quiz, selected_chapter, fallback_value=[])
                    
                    if files:
                        st.success(f"📂 プリントが {len(files)} 件見つかりました！")
                        for file in files:
                            with st.container(border=True):
                                c1, c2 = st.columns([8, 2])
                                c1.markdown(f"📄 **{file.get('name')}**")
                                link = file.get('webViewLink')
                                if link: c2.link_button("👁️ 開く・印刷", link, use_container_width=True)
                    else:
                        st.info("📂 この場所にプリントはまだ登録されていません。")

    with tab_exam:
        st.subheader("🏫 定期テストの過去問を探す")
        selected_school = st.selectbox("🏫 学校名を選択", ["-- 選択してください --"] + school_names, key="sel_e_sch")
        
        if selected_school != "-- 選択してください --":
            with st.spinner("年度・学期のフォルダを探しています..."):
                exam_folders = robust_api_call(list_library_folders, CAT_EXAM, selected_school, fallback_value=[])
            
            selected_exam_chap = None
            if exam_folders:
                selected_exam_chap = st.selectbox("📅 年度・テスト時期を選択", ["-- 選択してください --", "-- 直下のファイル --"] + exam_folders, key="sel_e_chap")
            
            if not exam_folders or (exam_folders and selected_exam_chap and selected_exam_chap != "-- 選択してください --"):
                with st.spinner("書庫からPDFを探しています...🔍"):
                    files = robust_api_call(list_library_files, CAT_EXAM, selected_school, selected_exam_chap, fallback_value=[])
                
                if files:
                    st.success(f"📂 過去問が {len(files)} 件見つかりました！")
                    for file in files:
                        with st.container(border=True):
                            c1, c2 = st.columns([8, 2])
                            c1.markdown(f"📄 **{file.get('name')}**")
                            link = file.get('webViewLink')
                            if link: c2.link_button("👁️ 開く・印刷", link, use_container_width=True)
                else:
                    st.info("📂 この場所に過去問はまだ登録されていません。")

    # ==========================================
    # 📤 アップロードエリア（管理者専用）
    # ==========================================
    if is_admin:
        st.divider()
        st.markdown("### 🔐 【管理者専用】新しい教材を登録する")
        
        with st.expander("➕ 教材をクラウド書庫にアップロード", expanded=False):
            # 🌟 修正: st.form を外し、リアルタイムにUIが変化するように変更！
            u_cat = st.selectbox("📂 登録するカテゴリー", [CAT_QUIZ, CAT_EXAM])
            u_sub_cat = st.text_input("🏷️ テキスト名 または 学校名（必須）", placeholder="例：ターゲット1200 / 田端中学校")
            
            uploaded_files = st.file_uploader(
                "📄 アップロードするPDF（複数選択できます！）", 
                type=["pdf", "png", "jpg", "jpeg"], 
                accept_multiple_files=True
            )
            
            # 🌟 複数ファイルが選ばれたら、ファイルごとに設定欄を出す！
            if uploaded_files:
                st.markdown("#### ⚙️ 各ファイルの設定（保存先フォルダ・ファイル名）")
                st.info("💡 単元・章の欄に入力した名前のフォルダが自動で作成されます！")
                
                file_settings = []
                for i, file_obj in enumerate(uploaded_files):
                    with st.container(border=True):
                        st.markdown(f"**📄 {file_obj.name}**")
                        c_chap, c_name = st.columns(2)
                        
                        # 拡張子なしのファイル名をデフォルトの「章」としてセット
                        default_chap = os.path.splitext(file_obj.name)[0]
                        
                        chap_val = c_chap.text_input("📖 単元・章（フォルダ名）", value=default_chap, key=f"chap_{i}")
                        name_val = c_name.text_input("📝 保存するファイル名", value=file_obj.name, key=f"name_{i}")
                        
                        file_settings.append({
                            "obj": file_obj,
                            "chap": chap_val,
                            "name": name_val
                        })
                
                # 登録ボタン
                submit_upload = st.button("🚀 この設定で教材を一括登録する", type="primary", use_container_width=True)
                
                if submit_upload:
                    if not u_sub_cat:
                        st.error("⚠️ テキスト名 または 学校名 を入力してください。")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        success_count = 0
                        error_messages = []
                        
                        for i, setting in enumerate(file_settings):
                            f_obj = setting["obj"]
                            f_chap = setting["chap"]
                            f_name = setting["name"]
                            
                            status_text.text(f"アップロード中... ({i+1}/{len(file_settings)}): {f_name}")
                            
                            file_bytes = f_obj.getvalue()
                            mime_type = f_obj.type
                            
                            success, result = robust_api_call(
                                upload_library_file,
                                u_cat,
                                u_sub_cat,
                                f_chap,  # 個別に入力した章を渡す
                                f_name,  # 個別に入力した名前を渡す
                                file_bytes,
                                mime_type,
                                fallback_value=(False, "APIエラー")
                            )
                            
                            if success:
                                success_count += 1
                            else:
                                error_messages.append(f"{f_name}: {result}")
                                
                            progress_bar.progress((i + 1) / len(file_settings))
                        
                        status_text.empty()
                        
                        if success_count == len(file_settings):
                            st.success(f"🎉 【{u_sub_cat}】に {success_count}件 のファイルを登録しました！")
                            time.sleep(2)
                            st.rerun()
                        elif success_count > 0:
                            st.warning(f"⚠️ {success_count}件 登録しましたが、一部失敗しました。")
                            for err in error_messages:
                                st.error(err)
                        else:
                            st.error("すべてのアップロードに失敗しました。")
                            for err in error_messages:
                                st.error(err)