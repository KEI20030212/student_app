import streamlit as st
import pandas as pd
import time
import re
import unicodedata 

# 先ほど作った共通防御関数をインポート
from utils.api_guard import robust_api_call
from utils.g_sheets import (
    get_all_student_names, 
    load_all_data, 
    load_billing_data, 
    save_billing_data,
    get_student_master_data,
    load_price_master
)
from utils.pdf_generator import generate_invoice_pdf

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
# 💡 フリーズ感を防ぐため show_spinner にメッセージを追加
@st.cache_data(show_spinner="☁️ 授業データを集計中...")
def fetch_all_student_data_cached(student_names):
    """
    全生徒の授業データを一括取得してキャッシュする関数。
    robust_api_call を使って個別の通信エラーも防ぐ。
    """
    all_data_list = []
    total_students = len(student_names)
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, s_name in enumerate(student_names):
        status_text.text(f"📥 授業データを取得中 ({i+1}/{total_students}): {s_name}")
        
        # 個別の生徒データ取得を防御
        df = robust_api_call(load_all_data, s_name, fallback_value=pd.DataFrame())
        
        if not df.empty:
            df['生徒名'] = s_name
            all_data_list.append(df)
            
        progress_bar.progress((i + 1) / total_students)
        # API制限（Rate Limit）を考慮した微小な待機
        time.sleep(0.1) 

    progress_bar.empty()
    status_text.empty()
    return all_data_list

def render_tuition_dashboard_page():
    st.header("💴 月謝（請求額）管理ダッシュボード")

    # --- 1. 基本マスタデータの取得（防御付き） ---
    student_names = robust_api_call(get_all_student_names, fallback_value=[])
    student_master = robust_api_call(get_student_master_data, fallback_value={})
    price_master = robust_api_call(load_price_master, fallback_value=pd.DataFrame())
    
    # マスタのゆらぎ補正
    if not price_master.empty and '学年' in price_master.columns and 'コマ数' in price_master.columns:
        price_master['学年'] = price_master['学年'].astype(str).apply(lambda x: unicodedata.normalize('NFKC', x).strip())
        price_master['コマ数'] = pd.to_numeric(price_master['コマ数'], errors='coerce').fillna(0).astype(int)

    # --- 2. 授業データの集計と年月リストの作成 ---
    month_options = ["データなし"]
    df_all = pd.DataFrame()
    all_data_list = []

    if student_names:
        all_data_list = fetch_all_student_data_cached(student_names)
        if all_data_list:
            df_all = pd.concat(all_data_list, ignore_index=True)
            if '日時' in df_all.columns:
                df_all['日時'] = pd.to_datetime(df_all['日時'], format='mixed', errors='coerce')
                df_all = df_all.dropna(subset=['日時'])
                df_all['年月'] = df_all['日時'].dt.strftime("%Y年%m月")
                month_options = sorted(df_all['年月'].unique().tolist(), reverse=True)
        else:
            from datetime import datetime
            month_options = [datetime.now().strftime("%Y年%m月")]

    # --- 3. 🌟 UI: 請求月の選択と更新ボタン（上部に横並び配置） ---
    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        selected_month = st.selectbox("📅 請求月を選択", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            # このページ用のキャッシュだけをピンポイントでクリア
            fetch_all_student_data_cached.clear()
            st.toast("最新データを取得します...", icon="⏳")
            st.rerun()

    st.divider()

    # --- ⚠️ エラーハンドリング（ボタンの下に配置して常に更新可能にする） ---
    if not student_names: 
        st.warning("⚠️ 生徒データが見つからないか、通信エラーが発生しました。上の更新ボタンを押して再試行してください。")
        return
        
    if selected_month == "データなし":
        st.info("集計対象のデータがありません。")
        return

    # --- 4. 請求額の計算ロジック ---
    if all_data_list and not df_all.empty:
        df_month = df_all[df_all['年月'] == selected_month]
    else:
        df_month = pd.DataFrame(columns=['生徒名'])

    st.subheader(f"👤 {selected_month} の請求設定")
    force_recalc = st.checkbox("🔄 過去の保存データを無視して、現在の料金マスタで強制的に再計算する")

    actual_koma_dict = {s: len(df_month[df_month['生徒名'] == s]) for s in student_names}
    
    # 保存済みデータの読み込みを防御
    saved_billing_df = robust_api_call(load_billing_data, selected_month, fallback_value=pd.DataFrame())

    table_data = []
    missing_master_warnings = [] 

    for student in student_names:
        actual_koma = actual_koma_dict.get(student, 0)
        m_info = student_master.get(student, {"学年": "未設定", "契約コース": "未設定", "特別割引コマ": 0})
        
        grade = unicodedata.normalize('NFKC', str(m_info["学年"])).strip()
        master_course = unicodedata.normalize('NFKC', str(m_info["契約コース"])).strip()
        
        # 割引コマの数値抽出
        raw_discount = str(m_info.get("特別割引コマ", "0")).strip()
        discount_nums = re.findall(r'\d+', raw_discount)
        discount_koma = int(discount_nums[0]) if discount_nums else 0

        course = master_course
        saved_price = None
        saved_extra_count = 0
        
        # 保存データがある場合の処理
        if not saved_billing_df.empty and '👤 生徒名' in saved_billing_df.columns and student in saved_billing_df['👤 生徒名'].values:
            row = saved_billing_df[saved_billing_df['👤 生徒名'] == student].iloc[0]
            course = next((row[c] for c in saved_billing_df.columns if "契約コース" in c), master_course)
            saved_price = next((row[c] for c in saved_billing_df.columns if "請求額" in c), None)
            
            try:
                saved_extra_count = int(next((row[c] for c in saved_billing_df.columns if "追加コマ" in c), 0))
                discount_koma = int(next((row[c] for c in saved_billing_df.columns if "割引コマ" in c), discount_koma))
            except:
                pass

        # コース名から基本コマ数を抽出 (例: "週2回(8コマ)" -> 8)
        try:
            koma_nums = re.findall(r'\d+', course)
            base_koma = int(koma_nums[0]) if koma_nums else 0
        except:
            base_koma = 0
            
        actual_extra_count = max(0, actual_koma - base_koma)
        
        # 料金マスタとの照合
        match = pd.DataFrame()
        if not price_master.empty and '学年' in price_master.columns and 'コマ数' in price_master.columns:
            match = price_master[(price_master['学年'] == grade) & (price_master['コマ数'] == base_koma)]
        
        if not match.empty:
            base_price = int(match.iloc[0]['料金'])
            unit_extra_price = int(match.iloc[0]['追加単価'])
        else:
            missing_master_warnings.append(f"{student} さん (学年: {grade}, コマ数: {base_koma})")
            base_price, unit_extra_price = 0, 0
            
        discount_amount = discount_koma * unit_extra_price
        calculated_price = max(0, base_price + (actual_extra_count * unit_extra_price) - discount_amount)

        # 最終的な請求額の決定（保存値を使うか計算値を使うか）
        if force_recalc:
            price = calculated_price
        elif saved_price is not None and actual_extra_count == saved_extra_count:
            price = saved_price
        else:
            price = calculated_price 

        table_data.append({
            "👤 生徒名": student,
            "🎓 学年": grade,
            "📚 契約コース": course,
            "📝 実際の受講数": actual_koma,
            "➕ 追加コマ": actual_extra_count,
            "🉐 割引コマ": discount_koma, 
            "💴 今月の請求額 (円)": int(price)
        })
    
    # 警告表示
    if missing_master_warnings:
        st.error("以下の生徒の料金設定が「料金マスタ」に見つかりません。")
        for w in missing_master_warnings:
            st.write(f"- {w}")

    display_df = pd.DataFrame(table_data)

    # --- 5. 編集・保存セクション ---
    with st.form("billing_form"):
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            disabled=["👤 生徒名", "🎓 学年", "📝 実際の受講数", "➕ 追加コマ", "🉐 割引コマ"] 
        )
        submitted = st.form_submit_button("💾 確定して保存", type="primary", use_container_width=True)
                
        if submitted:
            with st.spinner("☁️ 保存中..."):
                save_df = edited_df.drop(columns=["📝 実際の受講数"])
                # 保存処理を防御
                success = robust_api_call(save_billing_data, selected_month, save_df, fallback_value=False)
                
                if success is not False:
                    st.success("✅ 保存しました！")
                    st.cache_data.clear() # 月謝データの保存後は関連する他画面にも影響が出るため全体クリア推奨
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 通信エラーにより保存に失敗しました。")

    # 合計表示
    st.divider()
    total = edited_df["💴 今月の請求額 (円)"].sum() if not edited_df.empty else 0
    st.metric(label=f"🌟 {selected_month} の合計請求額", value=f"{total:,} 円")

    # --- 6. 📄 PDF発行セクション ---
    st.divider()
    st.subheader("📄 請求書PDFの発行")
    target_student = st.selectbox("請求書を発行する生徒を選択してください", student_names)
    
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
                    type="primary" # こちらも目立たせました
                )
            except Exception as e:
                st.error(f"⚠️ PDF生成エラー: {e}")