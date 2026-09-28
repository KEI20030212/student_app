import streamlit as st
import pandas as pd
import time
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
    
    # --- タブ1: 小テスト・確認テスト ---
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

    # --- タブ2: 定期テスト過去問 ---
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
        st.markdown("### 🔐 【管理者専用】新しい教材を登録する（一括登録対応）")
        
        with st.expander("➕ 教材をクラウド書庫にアップロード", expanded=False):
            with st.form("upload_library_form"):
                u_cat = st.selectbox("📂 登録するカテゴリー", [CAT_QUIZ, CAT_EXAM])
                
                c_sub, c_chap = st.columns(2)
                u_sub_cat = c_sub.text_input("🏷️ テキスト名 または 学校名（必須）", placeholder="例：ターゲット1200 / 田端中学校")
                u_chap = c_chap.text_input("📖 単元・章・年度（任意）", placeholder="例：Day1 / 2026年1学期中間")
                
                # 🌟 変更点: accept_multiple_files=True に設定し、複数ファイルを選択可能にする
                uploaded_files = st.file_uploader(
                    "📄 アップロードするPDF（複数選択できます！）", 
                    type=["pdf", "png", "jpg", "jpeg"], 
                    accept_multiple_files=True
                )
                
                st.info("💡 複数のファイルを選択した場合、ファイル名には「元のファイル名」がそのまま使用されます。ファイル名を変更して保存したい場合は、1つずつアップロードしてください。")
                u_filename = st.text_input("📝 保存時のファイル名（※1つのファイルをアップロードする時のみ有効）", placeholder="例：Day1_問題.pdf")
                
                submit_upload = st.form_submit_button("🚀 選択した教材をまとめて書庫に登録する", type="primary")
                
                if submit_upload:
                    if not u_sub_cat:
                        st.error("⚠️ テキスト名 または 学校名 を入力してください。")
                    elif not uploaded_files or len(uploaded_files) == 0:
                        st.error("⚠️ ファイルが選択されていません。")
                    else:
                        # 🌟 複数ファイル対応のアップロード処理
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        success_count = 0
                        error_messages = []
                        
                        for i, file_obj in enumerate(uploaded_files):
                            # 進捗の表示
                            status_text.text(f"アップロード中... ({i+1}/{len(uploaded_files)}): {file_obj.name}")
                            
                            file_bytes = file_obj.getvalue()
                            mime_type = file_obj.type
                            
                            # 1つのファイルで、かつファイル名の指定があればそれを使う。それ以外は元の名前。
                            if len(uploaded_files) == 1 and u_filename:
                                final_filename = u_filename
                            else:
                                final_filename = file_obj.name
                                
                            success, result = robust_api_call(
                                upload_library_file,
                                u_cat,
                                u_sub_cat,
                                u_chap,
                                final_filename,
                                file_bytes,
                                mime_type,
                                fallback_value=(False, "APIエラー")
                            )
                            
                            if success:
                                success_count += 1
                            else:
                                error_messages.append(f"{final_filename}: {result}")
                                
                            # プログレスバーを更新
                            progress_bar.progress((i + 1) / len(uploaded_files))
                        
                        status_text.empty()
                        
                        # 🌟 最終結果の表示
                        msg = f"【{u_sub_cat}】"
                        if u_chap: msg += f" ＞ 【{u_chap}】"
                        
                        if success_count == len(uploaded_files):
                            st.success(f"🎉 {msg} に {success_count}件 のファイルをまとめて登録しました！")
                            time.sleep(2)
                            st.rerun()
                        elif success_count > 0:
                            st.warning(f"⚠️ {msg} に {success_count}件 登録しましたが、一部失敗しました。")
                            for err in error_messages:
                                st.error(err)
                        else:
                            st.error("すべてのアップロードに失敗しました。")
                            for err in error_messages:
                                st.error(err)