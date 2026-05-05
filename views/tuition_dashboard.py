import streamlit as st
import pandas as pd
import time
import re
import unicodedata 

from utils.api_guard import robust_api_call
# 🌟 変更: 個別データ取得関数を全削除し、一括取得関数に統一
from utils.g_sheets import (
    get_all_logs, 
    get_student_master,
    load_billing_data, 
    save_billing_data,
    load_price_master
)
from utils.pdf_generator import generate_invoice_pdf

# 🌟 データを一括で爆速取得するためのキャッシュ関数
@st.cache_data(ttl=60)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=3600)
def cached_load_price_master():
    return robust_api_call(load_price_master, fallback_value=pd.DataFrame())

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")

    # --- 1. 基本マスタデータの取得（たった2回の通信！） ---
    df_students = cached_get_student_master()
    price_master = cached_load_price_master()
    
    # 🌟 ゆらぎ補正
    if not price_master.empty and '学年' in price_master.columns and 'コマ数' in price_master.columns:
        price_master['学年'] = price_master['学年'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        price_master['コマ数'] = pd.to_numeric(price_master['コマ数'], errors='coerce').fillna(0).astype(int)
        
        if '受験区分' in price_master.columns:
            price_master['受験区分'] = price_master['受験区分'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        if '学校区分' in price_master.columns:
            price_master['学校区分'] = price_master['学校区分'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())

    # --- 2. 授業データの集計と年月リストの作成（統合シートから一括取得！） ---
    month_options = ["データなし"]
    
    with st.spinner("☁️ 授業データを集計中...（超高速🚀）"):
        df_all_logs = cached_get_all_logs()
        
    if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns and '日時' in df_all_logs.columns:
        # 🌟 列名の揺れを吸収
        name_col = '名前' if '名前' in df_all_logs.columns else '生徒名'
        df_all_logs = df_all_logs.rename(columns={name_col: '生徒名'})
        
        df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
        df_all_logs = df_all_logs.dropna(subset=['日時'])
        df_all_logs['年月'] = df_all_logs['日時'].dt.strftime("%Y年%m月")
        month_options = sorted(df_all_logs['年月'].unique().tolist(), reverse=True)
    else:
        from datetime import datetime
        month_options = [datetime.now().strftime("%Y年%m月")]

    # --- 3. UI: 請求月の選択と更新ボタン ---
    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        selected_month = st.selectbox("📅 請求月を選択", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            st.cache_data.clear() # 🌟 アプリ全体のキャッシュを綺麗にリセット
            st.toast("最新の授業データと料金マスタを取得します...", icon="⏳")
            time.sleep(0.5)
            st.rerun()

    st.divider()

    # --- ⚠️ エラーハンドリング ---
    if df_students.empty: 
        st.warning("⚠️ 生徒データが見つからないか、通信エラーが発生しました。上の更新ボタンを押して再試行してください。")
        return
        
    if selected_month == "データなし":
        st.info("集計対象のデータがありません。")
        return

    # --- 4. 請求額の計算ロジック ---
    df_month = df_all_logs[df_all_logs['年月'] == selected_month] if not df_all_logs.empty else pd.DataFrame(columns=['生徒名'])

    st.subheader(f"👤 {selected_month} の請求設定")
    force_recalc = st.checkbox("🔄 過去の保存データを無視して、現在の料金マスタで強制的に再計算する")

    # その月の受講コマ数を集計
    actual_koma_dict = df_month['生徒名'].value_counts().to_dict()
    
    saved_billing_df = robust_api_call(load_billing_data, selected_month, fallback_value=pd.DataFrame())

    table_data = []
    missing_master_warnings = [] 

    # 🌟 DataFrame化されたマスターを使ってループ
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
            except:
                pass

        try:
            koma_nums = re.findall(r'\d+', course)
            base_koma = int(koma_nums[0]) if koma_nums else 0
        except:
            base_koma = 0
            
        actual_extra_count = max(0, actual_koma - base_koma)
        
        match = pd.DataFrame()
        if not price_master.empty and '学年' in price_master.columns and 'コマ数' in price_master.columns:
            mask = (price_master['学年'] == grade) & (price_master['コマ数'] == base_koma)
            if '受験区分' in price_master.columns: mask = mask & (price_master['受験区分'] == exam_status)
            if '学校区分' in price_master.columns: mask = mask & (price_master['学校区分'] == school_type)
            match = price_master[mask]
        
        if not match.empty:
            base_price = int(match.iloc[0]['料金'])
            unit_extra_price = int(match.iloc[0]['追加単価'])
        else:
            missing_master_warnings.append(f"{student} さん (学年: {grade}, コマ数: {base_koma}, 受験区分: {exam_status}, 学校区分: {school_type})")
            base_price, unit_extra_price = 0, 0
            
        discount_amount = discount_koma * unit_extra_price
        calculated_price = max(0, base_price + (actual_extra_count * unit_extra_price) - discount_amount)

        if force_recalc:
            price = calculated_price
        elif saved_price is not None and actual_extra_count == saved_extra_count:
            price = saved_price
        else:
            price = calculated_price 

        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "🏫 区分": f"{school_type} / {exam_status}",
            "📚 契約コース": course,
            "📝 実際の受講数": actual_koma,
            "➕ 追加コマ": actual_extra_count,
            "🉐 割引コマ": discount_koma, 
            "💴 今月の請求額 (円)": int(price)
        })
    
    if missing_master_warnings:
        st.error("⚠️ 以下の生徒の条件に完全一致する設定が「料金マスタ」に見つかりません。")
        for w in missing_master_warnings:
            st.write(f"- {w}")

    display_df = pd.DataFrame(table_data)

    # --- 5. 編集・保存セクション ---
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

    # --- 6. 📄 PDF発行セクション ---
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