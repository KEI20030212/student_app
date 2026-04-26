import streamlit as st
import pandas as pd
import math
import time
import zipfile
import io
import unicodedata

# 🌟 共通の防御関数をインポート
from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_instructor_master, 
    update_instructor_master,
    publish_salary_data
)
from utils.pdf_generator import generate_payslip_pdf

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
@st.cache_data(show_spinner="☁️ 生徒ごとの授業データを集計中...")
def fetch_salary_student_data_cached(student_names):
    """全生徒の授業データを一括取得してキャッシュ"""
    all_data_list = []
    total_students = len(student_names)
    
    p_bar = st.progress(0)
    t_status = st.empty()
    
    for i, s_name in enumerate(student_names):
        t_status.text(f"📥 {s_name} さんのデータを読み込み中... ({i+1}/{total_students})")
        df = robust_api_call(load_all_data, s_name, fallback_value=pd.DataFrame())
        if not df.empty:
            df['生徒名'] = s_name
            all_data_list.append(df)
        p_bar.progress((i + 1) / total_students)
    
    t_status.empty()
    p_bar.empty()
    return all_data_list

@st.cache_data(show_spinner="☁️ 講師マスタを読み込み中...")
def fetch_instructor_master_cached():
    """講師マスタを取得・キャッシュ"""
    df = robust_api_call(load_instructor_master, fallback_value=pd.DataFrame())
    if df.empty or "講師名" not in df.columns:
        return pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])
    return df

def render_salary_dashboard_page():
    st.header("💰 給与・交通費ダッシュボード")

    # --- 1. データ取得（まずはベースとなるデータを揃える） ---
    df_instructors = fetch_instructor_master_cached()
    student_names = robust_api_call(get_all_student_names, fallback_value=[])

    if not student_names:
        st.warning("⚠️ 生徒名リストを取得できませんでした。更新ボタンを押してください。")
        # 更新ボタンは下に配置するのでここではreturn
    
    # --------------------------------------------------------
    # 🌟 操作パネル（損益ダッシュボードと統一）
    # --------------------------------------------------------
    # 先に全データをロードして年月リストを作る
    all_data_list = fetch_salary_student_data_cached(student_names)
    month_options = ["データなし"]
    df_all = pd.DataFrame()
    
    if all_data_list:
        df_all = pd.concat(all_data_list, ignore_index=True)
        if '日時' in df_all.columns:
            df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
            df_all = df_all.dropna(subset=['日時'])
            df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
            month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)

    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    with col_month:
        selected_month = st.selectbox("📅 集計する月を選択", month_options)
    with col_btn:
        if st.button("🔄 給与データを最新に更新", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.toast("最新データを取得中...", icon="⏳")
            st.rerun()

    st.divider()

    # --- 📋 メインコンテンツ（タブ分け） ---
    tab_calc, tab_master = st.tabs(["📊 給与計算・明細発行", "👨‍🏫 講師単価・設定変更"])

    # ==========================================
    # Tab 1: 給与計算・明細発行
    # ==========================================
    with tab_calc:
        if df_all.empty or selected_month == "データなし":
            st.info("集計対象のデータがありません。")
        else:
            # --- 給与計算ロジック ---
            df_month = df_all[df_all['年月'] == selected_month].copy()
            df_month['担当講師'] = df_month['担当講師'].astype(str)
            df_month_exploded = df_month.assign(担当講師=df_month['担当講師'].str.split(r'[\n,、]')).explode('担当講師')
            df_month_exploded['担当講師'] = df_month_exploded['担当講師'].str.strip()
            
            if '授業形態' in df_month_exploded.columns:
                df_month_exploded['授業形態'] = df_month_exploded['授業形態'].astype(str).apply(
                    lambda x: unicodedata.normalize('NFKC', x).replace(' ', '')
                )

            valid_teachers = [t for t in df_month_exploded['担当講師'].unique() if t not in ["未入力", "", "nan", "None"]]
            
            summary_list = []
            for teacher in valid_teachers:
                df_teacher = df_month_exploded[df_month_exploded['担当講師'] == teacher].copy()
                df_teacher['日付'] = df_teacher['日時'].dt.date
                df_teacher = df_teacher.drop_duplicates(subset=['生徒名', '日付', '授業コマ'])

                t_row_df = df_instructors[df_instructors["講師名"] == teacher]
                if t_row_df.empty:
                    # マスタにいない場合はデフォルト値
                    p11, p12, p13, trans, allowance = 1500, 1800, 2000, 0, 0
                else:
                    t_row = t_row_df.iloc[0]
                    def safe_int(val, d=0):
                        try: return int(float(val)) if not pd.isna(val) and val != "" else d
                        except: return d
                    p11 = safe_int(t_row.get('1:1単価', 1500), 1500)
                    p12 = safe_int(t_row.get('1:2単価', 1800), 1800)
                    p13 = safe_int(t_row.get('1:3単価', 2000), 2000)
                    trans = safe_int(t_row.get('交通費', 0), 0)
                    allowance = safe_int(t_row.get('役職手当', 0), 0)

                koma_11 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:1']) / 1)
                koma_12 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:2']) / 2)
                koma_13 = math.ceil(len(df_teacher[df_teacher['授業形態'] == '1:3']) / 3)

                total_koma = koma_11 + koma_12 + koma_13
                koma_salary = (koma_11 * p11) + (koma_12 * p12) + (koma_13 * p13)
                working_days = df_teacher['日付'].nunique()
                transport_total = working_days * trans
                final_salary = koma_salary + transport_total + allowance

                summary_list.append({
                    "👨‍🏫 担当講師": teacher, "合計コマ数": total_koma, "授業給 (円)": int(koma_salary),
                    "役職手当 (円)": int(allowance), "出勤日数": working_days, 
                    "交通費合計 (円)": int(transport_total), "💰 最終支給額 (円)": int(final_salary)
                })

            if summary_list:
                df_summary = pd.DataFrame(summary_list)
                st.subheader(f"📊 {selected_month} の給与一覧")
                st.dataframe(df_summary, hide_index=True, use_container_width=True)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📦 全員分の明細をZIP作成", use_container_width=True):
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for row_data in summary_list:
                                pdf_bytes = generate_payslip_pdf(row_data, selected_month)
                                zip_file.writestr(f"給与明細_{selected_month}_{row_data['👨‍🏫 担当講師']}.pdf", pdf_bytes)
                        st.download_button("📥 ZIPをダウンロード", zip_buffer.getvalue(), f"{selected_month}_給与明細.zip", "application/zip", type="primary", use_container_width=True)
                
                with c2:
                    if st.button(f"🚀 {selected_month} の給与を公開する", use_container_width=True):
                        with st.spinner("送信中..."):
                            success = robust_api_call(publish_salary_data, selected_month, df_summary, fallback_value=False)
                            if success: st.success("✅ 公開しました！")
                            else: st.error("⚠️ 送信に失敗しました。")

    # ==========================================
    # Tab 2: 講師単価・設定変更
    # ==========================================
    with tab_master:
        st.subheader("⚙️ 講師マスタの設定変更")
        
        # --- 1. 一人ずつ設定変更フォーム ---
        st.markdown("##### 👤 講師ごとの個別設定")
        target_teacher = st.selectbox("設定を変更する講師を選択してください", ["選択してください"] + df_instructors["講師名"].tolist())
        
        if target_teacher != "選択してください":
            # 選択された講師の現在のデータを取得
            current_vals = df_instructors[df_instructors["講師名"] == target_teacher].iloc[0]
            
            with st.form("individual_edit_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_11 = st.number_input("1:1 単価", value=int(current_vals['1:1単価']), step=100)
                    new_12 = st.number_input("1:2 単価", value=int(current_vals['1:2単価']), step=100)
                    new_13 = st.number_input("1:3 単価", value=int(current_vals['1:3単価']), step=100)
                with col2:
                    new_trans = st.number_input("1日あたりの交通費", value=int(current_vals['交通費']), step=10)
                    new_allowance = st.number_input("役職手当", value=int(current_vals['役職手当']), step=1000)
                
                if st.form_submit_button("✅ この内容で保存する", type="primary"):
                    # データフレームを更新
                    idx = df_instructors.index[df_instructors["講師名"] == target_teacher][0]
                    df_instructors.at[idx, '1:1単価'] = new_11
                    df_instructors.at[idx, '1:2単価'] = new_12
                    df_instructors.at[idx, '1:3単価'] = new_13
                    df_instructors.at[idx, '交通費'] = new_trans
                    df_instructors.at[idx, '役職手当'] = new_allowance
                    
                    with st.spinner("☁️ 保存中..."):
                        if robust_api_call(update_instructor_master, df_instructors, fallback_value=False):
                            st.cache_data.clear()
                            st.success(f"✅ {target_teacher} 先生の設定を更新しました！")
                            time.sleep(1)
                            st.rerun()
        
        st.divider()
        
        # --- 2. 講師マスタ一覧表示（閲覧用） ---
        st.markdown("##### 📋 講師設定一覧（確認用）")
        st.dataframe(df_instructors, hide_index=True, use_container_width=True)
        
        with st.expander("➕ 新しい講師を登録する（手動追加）"):
            with st.form("add_teacher_form"):
                new_name = st.text_input("講師名")
                if st.form_submit_button("新規登録"):
                    if new_name and new_name not in df_instructors["講師名"].tolist():
                        new_row = pd.DataFrame([{"講師名": new_name, "1:1単価": 1500, "1:2単価": 1800, "1:3単価": 2000, "交通費": 0, "役職手当": 0}])
                        updated_df = pd.concat([df_instructors, new_row], ignore_index=True)
                        robust_api_call(update_instructor_master, updated_df)
                        st.cache_data.clear()
                        st.rerun()