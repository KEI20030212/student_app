import streamlit as st
import pandas as pd
import time
import re
import unicodedata 

from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_all_logs, 
    get_student_master,
    load_billing_data, 
    save_billing_data,
    load_price_master,
    save_monthly_total,   # 🌟 追加
    load_monthly_totals   # 🌟 追加
)
from utils.pdf_generator import generate_invoice_pdf

@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=3600)
def cached_load_price_master():
    return robust_api_call(load_price_master, fallback_value=pd.DataFrame())

# 🌟 追加：売上推移用のキャッシュ
@st.cache_data(ttl=60)
def cached_load_monthly_totals():
    return robust_api_call(load_monthly_totals, fallback_value=pd.DataFrame())

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")

    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
    price_master = cached_load_price_master()
    
    if not price_master.empty and '学年' in price_master.columns and 'コマ数' in price_master.columns:
        price_master['学年'] = price_master['学年'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        price_master['コマ数'] = pd.to_numeric(price_master['コマ数'], errors='coerce').fillna(0).astype(int)
        
        if 'コース' in price_master.columns:
            price_master['コース'] = price_master['コース'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        if '受験区分' in price_master.columns:
            price_master['受験区分'] = price_master['受験区分'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        if '学校区分' in price_master.columns:
            price_master['学校区分'] = price_master['学校区分'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())

    month_options = ["データなし"]
    
    with st.spinner("☁️ 授業データを集計中...（超高速🚀）"):
        df_all_logs = cached_get_all_logs()
        
    if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns and '日時' in df_all_logs.columns:
        name_col = '名前' if '名前' in df_all_logs.columns else '生徒名'
        df_all_logs = df_all_logs.rename(columns={name_col: '生徒名'})
        
        df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
        df_all_logs = df_all_logs.dropna(subset=['日時'])
        df_all_logs['年月'] = df_all_logs['日時'].dt.strftime("%Y年%m月")
        month_options = sorted(df_all_logs['年月'].unique().tolist(), reverse=True)
    else:
        from datetime import datetime
        month_options = [datetime.now().strftime("%Y年%m月")]

    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        selected_month = st.selectbox("📅 請求月を選択", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.toast("最新の授業データと料金マスタを取得します...", icon="⏳")
            time.sleep(0.5)
            st.rerun()

    st.divider()

    if df_students.empty: 
        st.warning("⚠️ 生徒データが見つからないか、通信エラーが発生しました。上の更新ボタンを押して再試行してください。")
        return
        
    if selected_month == "データなし":
        st.info("集計対象のデータがありません。")
        return

    # 🌟 タブで画面を分割
    tab_calc, tab_trend = st.tabs(["💴 当月の計算・PDF発行", "📈 過去の売上推移グラフ"])

    # ==========================================
    # タブ1：当月の計算・PDF発行
    # ==========================================
    with tab_calc:
        df_month = df_all_logs[df_all_logs['年月'] == selected_month] if not df_all_logs.empty else pd.DataFrame(columns=['生徒名'])

        st.subheader(f"👤 {selected_month} の請求設定")
        
        c_fee1, c_fee2 = st.columns(2)
        global_admin_fee = c_fee1.number_input("🏢 今月の管理費・諸経費（一律加算）", min_value=0, value=3300, step=100)
        force_recalc = c_fee2.checkbox("🔄 過去の保存データを無視して、強制的に再計算する")

        actual_koma_dict = df_month['生徒名'].value_counts().to_dict()
        saved_billing_df = robust_api_call(load_billing_data, selected_month, fallback_value=pd.DataFrame())

        table_data = []
        missing_master_warnings = [] 

        for _, m_info in df_students.iterrows():
            student = str(m_info.get("生徒名", "")).strip()
            if not student: continue
            
            actual_koma = actual_koma_dict.get(student, 0)
            
            grade = unicodedata.normalize('NFKC', str(m_info.get("学年", "未設定"))).strip()
            master_course = unicodedata.normalize('NFKC', str(m_info.get("契約コース", "未設定"))).strip()
            exam_status = unicodedata.normalize('NFKC', str(m_info.get("受験区分", "未設定"))).strip()
            school_type = unicodedata.normalize('NFKC', str(m_info.get("学校区分", "未設定"))).strip()
            
            raw_discount = str(m_info.get("特別割引(コマ)", "0")).strip()
            discount_nums = re.findall(r'\d+', raw_discount)
            discount_koma = int(discount_nums[0]) if discount_nums else 0

            course = master_course
            saved_price = None
            saved_extra_count = 0
            
            if not force_recalc and not saved_billing_df.empty and '👤 生徒名' in saved_billing_df.columns and student in saved_billing_df['👤 生徒名'].values:
                row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
                course = next((row[c] for c in saved_billing_df.columns if "契約コース" in c), master_course)
                saved_price = next((row[c] for c in saved_billing_df.columns if "請求額" in c), None)
                
                try:
                    saved_extra_count = int(next((row[c] for c in saved_billing_df.columns if "追加コマ" in c), 0))
                    discount_koma = int(next((row[c] for c in saved_billing_df.columns if "割引コマ" in c), discount_koma))
                    saved_admin_fee = int(next((row[c] for c in saved_billing_df.columns if "管理費" in c), global_admin_fee))
                except:
                    saved_admin_fee = global_admin_fee
            else:
                saved_admin_fee = global_admin_fee

            course_list = []
            if course and course != "未設定":
                for part in course.replace('、', ',').replace('＋', ',').replace('+', ',').split(','):
                    part = part.strip()
                    if not part: continue
                    
                    nums = re.findall(r'\d+', part)
                    if nums:
                        koma = int(nums[0])
                        name_match = re.match(r'^([^0-9:：\-]+)', part)
                        c_name = name_match.group(1).strip() if name_match else "未設定"
                        course_list.append({"name": c_name, "koma": koma})

            total_base_price = 0
            total_base_koma = 0
            max_extra_unit_price = 0 
            
            if course_list:
                for c in course_list:
                    c_name = c["name"]
                    c_koma = c["koma"]
                    
                    base_mask = (price_master['学年'] == grade)
                    if 'コース' in price_master.columns and c_name != "未設定":
                        base_mask &= (price_master['コース'] == c_name)
                    if '学校区分' in price_master.columns: 
                        base_mask &= ((price_master['学校区分'] == school_type) | (price_master['学校区分'] == ""))
                    
                    perfect_mask = base_mask.copy()
                    if '受験区分' in price_master.columns:
                        perfect_mask &= (price_master['受験区分'] == exam_status)
                    
                    match_df = price_master[perfect_mask]
                    
                    if match_df.empty:
                        match_df = price_master[base_mask]
                    
                    if not match_df.empty:
                        if '追加単価' in match_df.columns and not pd.isna(match_df.iloc[0]['追加単価']):
                            unit_price = int(match_df.iloc[0]['追加単価'])
                        else:
                            master_koma = int(match_df.iloc[0]['コマ数']) if int(match_df.iloc[0]['コマ数']) > 0 else 1
                            unit_price = int(int(match_df.iloc[0]['料金']) / master_koma)
                            
                        calculated_base = unit_price * c_koma
                        
                        total_base_price += calculated_base
                        total_base_koma += c_koma
                        
                        if unit_price > max_extra_unit_price:
                            max_extra_unit_price = unit_price
                    else:
                        missing_master_warnings.append(f"{student} さん ({c_name} / 学年: {grade})")
                        total_base_koma += c_koma 
            else:
                total_base_price = 0
                total_base_koma = 0

            actual_extra_count = max(0, actual_koma - total_base_koma)
            discount_amount = discount_koma * max_extra_unit_price
            
            tuition_price = max(0, total_base_price + (actual_extra_count * max_extra_unit_price) - discount_amount)
            calculated_price = tuition_price + saved_admin_fee

            if force_recalc:
                price = calculated_price
                final_admin_fee = global_admin_fee
            elif saved_price is not None and actual_extra_count == saved_extra_count:
                price = saved_price
                final_admin_fee = saved_admin_fee
            else:
                price = calculated_price 
                final_admin_fee = saved_admin_fee

            table_data.append({
                "👤 生徒名": student,
                "🎓 学年": grade,
                "🏫 区分": f"{school_type} / {exam_status}",
                "📚 契約コース": course,
                "📝 実際の受講数": actual_koma,
                "➕ 追加コマ": actual_extra_count,
                "🉐 割引コマ": discount_koma, 
                "🏢 管理費": final_admin_fee,  
                "💴 今月の請求額 (円)": int(price)
            })
        
        if missing_master_warnings:
            st.error("⚠️ 以下の生徒の契約条件に一致する設定が「料金マスタ」に見つかりません。料金が0円として計算されています。")
            for w in missing_master_warnings:
                st.write(f"- {w}")

        display_df = pd.DataFrame(table_data)

        with st.form("billing_form"):
            edited_df = st.data_editor(
                display_df,
                hide_index=True,
                use_container_width=True,
                disabled=["👤 生徒名", "🎓 学年", "🏫 区分", "📝 実際の受講数", "➕ 追加コマ", "🉐 割引コマ"] 
            )
            submitted = st.form_submit_button("💾 確定して保存", type="primary", use_container_width=True)
                    
            if submitted:
                with st.spinner("☁️ 保存中..."):
                    save_df = edited_df.drop(columns=["📝 実際の受講数", "🏫 区分"]) 
                    success = robust_api_call(save_billing_data, selected_month, save_df, fallback_value=False)
                    
                    # 🌟 追加：今月の合計額を「月別売上推移」にも自動保存する！
                    total_to_save = int(save_df["💴 今月の請求額 (円)"].sum())
                    robust_api_call(save_monthly_total, selected_month, total_to_save, fallback_value=False)
                    
                    if success is not False:
                        st.success("✅ 保存しました！")
                        st.cache_data.clear() 
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 通信エラーにより保存に失敗しました。")

        st.divider()
        total = edited_df["💴 今月の請求額 (円)"].sum() if not edited_df.empty else 0
        st.metric(label=f"🌟 {selected_month} の合計請求額", value=f"{total:,} 円")

        st.divider()
        st.subheader("📄 請求書PDFの発行")
        target_student = st.selectbox("請求書を発行する生徒を選択してください", df_students['生徒名'].tolist() if not df_students.empty else [])
        
        if target_student:
            pdf_rows = edited_df[edited_df["👤 生徒名"] == target_student].to_dict('records')
            if pdf_rows:
                pdf_data = pdf_rows[0]
                try:
                    pdf_file = generate_invoice_pdf(pdf_data, selected_month)
                    st.download_button(
                        label=f"📥 {target_student} 様の請求書をダウンロード",
                        data=pdf_file,
                        file_name=f"請求書_{selected_month}_{target_student}.pdf",
                        mime="application/pdf",
                        type="primary" 
                    )
                except Exception as e:
                    st.error(f"⚠️ PDF生成エラー: {e}")

    # ==========================================
    # タブ2：過去の売上推移グラフ
    # ==========================================
    with tab_trend:
        st.subheader("📈 月別売上（請求総額）の推移")
        st.write("各月に確定保存された合計請求額の履歴グラフです。")
        
        df_trends = cached_load_monthly_totals()
        
        if df_trends.empty:
            st.info("まだ保存された売上データがありません。「当月の計算」タブで確定保存を行うとここにグラフが表示されます。")
        else:
            # データを年月順に並び替え
            df_trends['年月ソート用'] = pd.to_datetime(df_trends['年月'].str.replace('年', '/').str.replace('月', ''), format='%Y/%m', errors='coerce')
            df_trends = df_trends.sort_values('年月ソート用').dropna()
            
            # グラフ表示用にインデックスを年月にする
            df_chart = df_trends.set_index('年月')[['合計請求額']]
            
            st.bar_chart(df_chart, use_container_width=True)
            
            # データテーブルも表示
            st.write("##### 📋 データ詳細")
            st.dataframe(df_trends[['年月', '合計請求額']].sort_values('年月', ascending=False), hide_index=True)