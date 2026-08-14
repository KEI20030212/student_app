import streamlit as st
import time
import pandas as pd
import datetime
import re

from utils.g_sheets import (
    get_student_master, 
    get_student_info, 
    update_student_info,
    move_student_to_inactive_sheet,
    get_all_logs,
    sync_self_study_settings_add,       # 🌟 追加：自習シートに自動追加する機能
    sync_self_study_settings_remove     # 🌟 追加：自習シートから自動削除する機能
)
from utils.api_guard import robust_api_call

from views.student_details import render_student_details_page
from views.analysis import render_analysis_page
from views.conference_report import render_conference_report
from views.admin_tools import render_admin_tools_page 

def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

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
    # get_student_master を使って「ID - 名前」のリストを生成
    # ==========================================
    student_options = []
    with st.spinner("生徒データを読み込み中..."):
        df_students = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
        if not df_students.empty and '生徒ID' in df_students.columns and '生徒名' in df_students.columns:
            student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
            
    selected_student = st.selectbox("👤 対象の生徒を選択してください", student_options, index=None, placeholder="--選択--")

    if is_conference_mode:
        st.sidebar.success("✅ 面談モードON（読取専用）")
        st.sidebar.caption("※保護者と一緒に画面を見るためのモードです。")
    else:
        st.sidebar.info("✏️ 通常モード（入力・編集）")

    # ==========================================
    # 生徒が選ばれていない時の処理
    # ==========================================
    if selected_student is None:
        
        if st.session_state.get('role') in ['admin', 'owner', 'head_teacher'] and not is_conference_mode:
            
            if 'flash_success_msg' in st.session_state:
                st.success(st.session_state['flash_success_msg'])
                del st.session_state['flash_success_msg'] 
            
            st.divider()

            # ==========================================
            # 1️⃣ 新入生追加
            # ==========================================
            form_placeholder = st.empty()
            
            with form_placeholder.container():
                with st.expander("🆕 新入生アカウントを新しく登録する", expanded=False):
                    with st.form("add_new_student_form"):
                        st.markdown("##### 📝 基本情報の入力")
                        
                        branch_opts = {
                            "田端新町校": "t",
                            "東十条駅前校": "h",
                            "プレフィックスなし (数字のみ)": ""
                        }
                        selected_branch_key = st.selectbox("🏫 所属校舎（生徒IDの頭文字になります）", list(branch_opts.keys()), index=0)
                        
                        if not df_students.empty and '生徒ID' in df_students.columns:
                            existing_ids = pd.to_numeric(df_students['生徒ID'].astype(str).str.extract(r'(\d+)')[0], errors='coerce').dropna()
                            next_num = int(existing_ids.max() + 1) if not existing_ids.empty else 1
                        else:
                            next_num = 1
                        
                        st.caption(f"🤖 生徒IDは自動で振られます ➡ **【 (校舎頭文字) + {next_num:03d} 】** （例: A{next_num:03d}）")
                        
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
                    
            if submit_new_student:
                if not new_name.strip():
                    st.error("❌ 生徒名を入力してください。")
                else:
                    branch_prefix = branch_opts[selected_branch_key]
                    final_student_id = f"{branch_prefix}{next_num:03d}" if branch_prefix else str(next_num)
                    
                    course_parts = []
                    if b_val > 0: course_parts.append(f"Bコース:{b_val}")
                    if q_val > 0: course_parts.append(f"Qコース:{q_val}")
                    new_contract_str = "、".join(course_parts)
                    
                    new_type_str = "、".join(new_types)
                    
                    with st.spinner("スプレッドシートに登録中..."):
                        def _create_student():
                            update_student_info(
                                student_id=final_student_id, 
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
                            # 🌟 マスター登録成功後、自習管理シートの「設定」にも自動で名前を追加！
                            robust_api_call(
                                sync_self_study_settings_add,
                                name=new_name.strip(),
                                grade_raw=new_grade.strip(),
                                fallback_value=(False, "")
                            )
                            
                            st.cache_data.clear()
                            form_placeholder.empty() 
                            st.session_state['flash_success_msg'] = f"🎉 新入生「{new_name}」さんのシステム登録が完了しました！（生徒ID: {final_student_id}）\n上のリストから名前を選択して、詳細データの入力を開始できます。"
                            st.success("✅ 登録成功！画面を更新します...")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("通信エラーにより登録できませんでした。もう一度お試しください。")
            st.write("")
            
            # ==========================================
            # 2️⃣ 退塾予備軍アラート
            # ==========================================
            df_logs = cached_get_all_logs()
            alert_students = []
            
            if not df_logs.empty and "APIエラー発生" not in df_logs.columns:
                name_col = '生徒名' if '生徒名' in df_logs.columns else '名前'
                
                if name_col in df_logs.columns and '集中力' in df_logs.columns and 'ミスへの反応' in df_logs.columns:
                    df_logs['日時'] = pd.to_datetime(df_logs['日時'], format='mixed', errors='coerce')
                    
                    for student_name, group in df_logs.groupby(name_col):
                        recent_logs = group.sort_values('日時', ascending=False).head(5)
                        if len(recent_logs) < 3: 
                            continue 
                            
                        attitude_neg_count = 0
                        attend_neg_count = 0
                        
                        for _, row in recent_logs.iterrows():
                            conc = str(row.get('集中力', ''))
                            reac = str(row.get('ミスへの反応', ''))
                            if conc in ["疲労気味", "ムラあり", "集中できない"] or reac in ["放置しようとした"]:
                                attitude_neg_count += 1
                                
                            attendance = str(row.get('出欠', ''))
                            late_time_raw = row.get('遅刻時間', 0)
                            try:
                                late_time = float(late_time_raw)
                            except (ValueError, TypeError):
                                late_time = 0
                                
                            if "欠席" in attendance or late_time > 0:
                                attend_neg_count += 1
                                
                        total_logs = len(recent_logs)
                        attitude_ratio = attitude_neg_count / total_logs
                        attend_ratio = attend_neg_count / total_logs
                        
                        is_attitude_alert = attitude_ratio >= 0.4
                        is_attend_alert = attend_ratio >= 0.4
                        
                        if is_attitude_alert or is_attend_alert:
                            max_ratio = max(attitude_ratio, attend_ratio)
                            reasons = []
                            if is_attitude_alert:
                                reasons.append(f"授業態度の悪化（{attitude_neg_count}回）")
                            if is_attend_alert:
                                reasons.append(f"遅刻・欠席の多発（{attend_neg_count}回）")
                                
                            alert_students.append({
                                "name": student_name,
                                "ratio": int(max_ratio * 100),
                                "reasons": reasons,
                                "total": total_logs
                            })
                            
            if alert_students:
                alert_students = sorted(alert_students, key=lambda x: x["ratio"], reverse=True)
                with st.container(border=True):
                    st.error("🚨 **【退塾予備軍アラート】最近の様子に変化が見られる生徒**")
                    st.caption("直近の5回の授業ログから「ネガティブな態度」や「遅刻・欠席の多発」が40%以上記録された生徒を自動検知しています。")
                    for ast in alert_students:
                        reason_text = " / ".join(ast['reasons'])
                        st.markdown(f"- 👤 **{ast['name']}** さん （危険度: **{ast['ratio']}%**） ➡ ⚠️ **理由:** {reason_text}")
                st.write("")

            # ==========================================
            # 3️⃣ 新年度一括処理
            # ==========================================
            render_admin_tools_page()
            st.divider()

        st.info("👆 上のメニューから生徒を選択すると、以下の個別メニューが利用できます！")
        return


    # ==========================================
    # 🌟 生徒が選ばれている時の処理
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
            
        # ==========================================
        # 🌟 退塾手続きエリア
        # ==========================================
        if st.session_state.get('role') in ['admin', 'owner', 'head_teacher']:
            st.write("")
            st.write("")
            st.divider()
            
            target_id = selected_student.split(" - ")[0]
            target_name = selected_student.split(" - ")[1]
            
            with st.expander(f"🚨 【管理者限定】{target_name} さんの退塾・アーカイブ手続き", expanded=False):
                st.warning(f"この操作を行うと、{target_name} さんのデータは「退塾生情報」シートに移動し、現役生リストから即座に除外されます。")
                
                confirm_archive = st.checkbox(f"本当に {target_name} さんの生徒データをアーカイブ（退塾処理）してよろしいですか？", key="chk_archive")
                
                if st.button(f"🚀 {target_name} さんの退塾処理を実行する", type="primary", use_container_width=True):
                    if not confirm_archive:
                        st.error("⚠️ 処理を実行するには、上記のチェックボックスにチェックを入れてください。")
                    else:
                        with st.spinner("データベースの引っ越し処理を実行中..."):
                            success, err_msg = robust_api_call(move_student_to_inactive_sheet, target_id, fallback_value=(False, "通信タイムアウト"))
                            
                            if success:
                                # 🌟 マスターから削除された直後、自習管理シートの「設定」からも自動で名前を削除！
                                robust_api_call(
                                    sync_self_study_settings_remove,
                                    name=target_name,
                                    fallback_value=(False, "")
                                )
                                
                                st.cache_data.clear()
                                st.session_state['flash_success_msg'] = f"✅ {target_name} さんの退塾アーカイブ処理が正常に完了しました。"
                                st.success("処理が完了しました！画面を更新します...")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error(f"❌ 処理に失敗しました。理由: {err_msg}")