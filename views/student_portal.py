import streamlit as st
import time
import pandas as pd
import datetime
import re

# 🌟 新規登録用に update_student_info もインポート
from utils.g_sheets import get_student_master, get_student_info, update_student_info
from utils.api_guard import robust_api_call

from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
from views.conference_report import render_conference_report

def render_student_portal_page():
    col_title, col_toggle = st.columns([3, 1])
    
    with col_title:
        st.header("🏫 生徒個別ポータル")
        
    with col_toggle:
        st.markdown("<br>", unsafe_allow_html=True) 
        is_conference_mode = st.toggle("👨‍👩‍👦 面談モード", value=False)
        
    if is_conference_mode:
        st.caption("✅ 面談モードON（読取専用）※保護者と一緒に画面を見るためのモードです。")

    # ==========================================
    # 🌟 get_student_master を使って「ID - 名前」のリストを生成
    # ==========================================
    student_options = []
    with st.spinner("生徒データを読み込み中..."):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
            student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
            
    # 🌟 全機能共通の生徒選択バー
    selected_student = st.selectbox("👤 対象の生徒を選択してください", student_options, index=None, placeholder="--選択--")

    if is_conference_mode:
        st.sidebar.success("✅ 面談モードON（読取専用）")
        st.sidebar.caption("※保護者と一緒に画面を見るためのモードです。")
    else:
        st.sidebar.info("✏️ 通常モード（入力・編集）")

    # ==========================================
    # 🌟 生徒が選ばれていない時の「機能紹介 ＆ 新入生登録画面」
    # ==========================================
    if selected_student is None:
        
        # 🆕 新入生登録フォーム（教室長・管理者のみ表示）
        if st.session_state.get('role') in ['admin', 'owner', 'head_teacher'] and not is_conference_mode:
            
            # 🌟 アップグレードポイント：画面更新後も残る「安心の完了メッセージ」
            if 'flash_success_msg' in st.session_state:
                st.success(st.session_state['flash_success_msg'])
                del st.session_state['flash_success_msg'] # 一度表示したら消す
            
            # 🌟 アップグレードポイント：フォーム全体を「あとで消せる箱」に入れる
            form_placeholder = st.empty()
            
            with form_placeholder.container():
                with st.expander("🆕 新入生アカウントを新しく登録する", expanded=False):
                    with st.form("add_new_student_form"):
                        st.markdown("##### 📝 基本情報の入力")
                        
                        if not df_students.empty and '生徒ID' in df_students.columns:
                            existing_ids = pd.to_numeric(df_students['生徒ID'].astype(str).str.extract(r'(\d+)')[0], errors='coerce').dropna()
                            next_id = int(existing_ids.max() + 1) if not existing_ids.empty else 1
                        else:
                            next_id = 1
                        
                        st.caption(f"🤖 生徒IDは自動で振られます ➡ **【 {next_id} 】**")
                        
                        new_name = st.text_input("生徒名（必須）", placeholder="例: 山田 太郎")
                        new_grade = st.text_input("学年", placeholder="例: 中3 / 高1")
                        
                        c_ex1, c_ex2 = st.columns(2)
                        exam_opts = ["", "受験生"]
                        new_exam = c_ex1.selectbox("🔥 受験区分", exam_opts, index=0)
                        
                        school_opts = ["", "公立", "私立・国立"]
                        new_school_type = c_ex2.selectbox("🏫 学校区分", school_opts, index=0)
                        
                        new_school = st.text_input("学校名", placeholder="例: ○○中学校")
                        new_target = st.text_input("志望校・通塾目的", placeholder="例: ○○高校合格 / 定期テスト対策")
                        new_subjects = st.text_input("受講科目", placeholder="例: 英語, 数学")
                        
                        st.divider()
                        st.markdown("##### 📋 契約コースの設定 (回数/月)")
                        cc1, cc2 = st.columns(2)
                        b_val = cc1.number_input("Bコース", min_value=0, value=0, step=1)
                        q_val = cc2.number_input("Qコース", min_value=0, value=0, step=1)
                        
                        st.divider()
                        st.markdown("##### 🎯 生徒タイプの初期設定")
                        type_opts = ["充実", "訓練", "実用", "関係", "自尊", "報酬"]
                        new_types = st.multiselect("生徒タイプ（複数選択可）", type_opts)
                        
                        submit_new_student = st.form_submit_button("🚀 新入生をシステムに登録する", type="primary")
                    
            # フォームの「外」で送信判定を行う（これによりフォームごと消す魔法が使える）
            if submit_new_student:
                if not new_name.strip():
                    st.error("❌ 生徒名を入力してください。")
                else:
                    course_parts = []
                    if b_val > 0: course_parts.append(f"Bコース:{b_val}")
                    if q_val > 0: course_parts.append(f"Qコース:{q_val}")
                    new_contract_str = "、".join(course_parts)
                    
                    new_type_str = "、".join(new_types)
                    
                    with st.spinner("スプレッドシートに登録中..."):
                        def _create_student():
                            update_student_info(
                                student_id=str(next_id),
                                name=new_name.strip(),
                                grade=new_grade.strip(),
                                school=new_school.strip(),
                                target=new_target.strip(),
                                subjects=new_subjects.strip(),
                                ability=3,
                                motivation=3,
                                naishin=3,
                                dev_score=50,
                                hw_rate=100,
                                exam_status=new_exam,
                                school_type=new_school_type,
                                contract_course=new_contract_str,
                                student_type=new_type_str
                            )
                            return True
                        
                        success = robust_api_call(_create_student, fallback_value=False)
                        
                        if success:
                            st.cache_data.clear()
                            
                            # 🌟 魔法1：登録成功した瞬間に「入力フォーム」を画面から完全に消し去る！
                            form_placeholder.empty() 
                            
                            # 🌟 魔法2：画面がリロードされた直後に表示するメッセージを仕込む！
                            st.session_state['flash_success_msg'] = f"🎉 新入生「{new_name}」さんのシステム登録が完了しました！\n上のリストから名前を選択して、詳細データの入力を開始できます。"
                            
                            st.success("✅ 登録成功！画面を更新します...")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("通信エラーにより登録できませんでした。もう一度お試しください。")
            st.write("")

        st.info("👆 上のメニューから生徒を選択すると、以下の個別メニューが利用できます！")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("### 👤 生徒詳細・成績入力")
                st.write("生徒の基本データや、テスト結果を管理します。")
                st.markdown("""
                - **🩺 カルテ**: 能力・やる気マトリクスの確認
                - **✍️ 成績入力**: 定期テスト・内申点・模試の入力
                - **📈 成績推移**: 過去の点数グラフの確認
                - """ if not is_conference_mode else "")
        with c2:
            with st.container(border=True):
                st.markdown("### 📊 個別分析・履歴・振替")
                st.write("日々の授業履歴や、未消化の振替授業を管理します。")
                st.markdown("""
                - **⚠️ 振替管理**: 未消化の授業コマ数を自動カウント
                - **📊 学習グラフ**: ページ数や単元ごとの点数を可視化
                - **📚 履歴編集**: 過去の授業記録をスプレッドシートに直接上書き修正
                - """ if not is_conference_mode else "")
        return


    # ==========================================
    # 🌟 モードの分岐
    # ==========================================
    if is_conference_mode:
        with st.spinner("面談用データを準備中..."):
            info = get_student_info(selected_student) 
            
        render_conference_report(selected_student, info)
        
    else:
        app_mode = st.radio(
            "📂 表示するメニューを選んでください", 
            ["👤 生徒詳細・成績入力", "📊 個別分析・履歴・振替管理"], 
            horizontal=True
        )
        
        st.divider()
        
        if app_mode == "👤 生徒詳細・成績入力":
            render_student_details_page(selected_student)
        else:
            render_analysis_page(selected_student)