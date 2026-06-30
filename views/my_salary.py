import streamlit as st
import pandas as pd
import time 

from utils.api_guard import robust_api_call
from utils.g_sheets import load_published_salary
from utils.pdf_generator import generate_payslip_pdf

# 👇 修正: @st.cache_data を削除！（キャッシュ管理は g_sheets.py に完全に任せる）
def get_my_salary_data_safe():
    """公開済みの給与データを取得・防御（キャッシュはg_sheets側で処理）"""
    with st.spinner("☁️ 給与データを取得中..."):
        return robust_api_call(load_published_salary, fallback_value=pd.DataFrame())

def render_my_salary_page():
    # ログインしている先生の名前を取得
    teacher_name = st.session_state.get('username', '先生')
    
    st.header(f"💴 {teacher_name} 先生の給与確認")
    st.write("※教室長から公開された確定済みの給与明細を表示しています。")

    # 👇 修正: 二重キャッシュを排除した新しい関数を呼び出す
    df_all_salaries = get_my_salary_data_safe()
    
    # --------------------------------------------------------
    # 操作パネル（月選択 ＆ 更新ボタン）
    # --------------------------------------------------------
    month_options = ["データなし"]
    my_data = pd.DataFrame()
    
    # データが存在する場合のみ、自分のデータに絞り込んで月のリストを作成
    if not df_all_salaries.empty and '👨‍🏫 担当講師' in df_all_salaries.columns:
        my_data = df_all_salaries[df_all_salaries['👨‍🏫 担当講師'] == teacher_name]
        if not my_data.empty and '年月' in my_data.columns:
            my_data = my_data.sort_values('年月', ascending=False).reset_index(drop=True)
            month_options = my_data['年月'].unique().tolist()

    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        selected_month = st.selectbox("📅 確認する月を選択してください", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            st.cache_data.clear() # g_sheets.py 側のキャッシュをクリア
            st.toast("最新データを取得します...", icon="⏳")
            time.sleep(0.5)
            st.rerun()

    st.divider()
    # --------------------------------------------------------

    # --- ⚠️ エラーハンドリング ---
    if df_all_salaries.empty:
        st.warning("現在、公開されている給与データはありません。通信エラーの可能性もあるため、上のボタンで更新をお試しください。")
        return
        
    if '👨‍🏫 担当講師' not in df_all_salaries.columns:
        st.error("⚠️ データに「担当講師」の項目が見つかりません。システム管理者（教室長）にお問い合わせください。")
        return
        
    if my_data.empty:
        st.info(f"現在、{teacher_name} 先生の公開済み給与データはありません。")
        return

    if selected_month == "データなし":
        return

    # --- 📊 給与データの表示 ---
    # 選んだ月のデータ行を取得
    selected_row = my_data[my_data['年月'] == selected_month].iloc[0]
    
    def safe_int(val):
        try:
            return int(float(val))
        except:
            return 0

    final_salary = safe_int(selected_row.get('💰 最終支給額 (円)', 0))
    class_salary = safe_int(selected_row.get('授業給 (円)', 0))
    transport_fee = safe_int(selected_row.get('交通費合計 (円)', 0))
    allowance = safe_int(selected_row.get('役職手当 (円)', 0))

    st.markdown(f"### 📊 {selected_month} の給与概要")
    col1, col2, col3 = st.columns(3)
    col1.metric("最終支給額", f"¥{final_salary:,}")
    col2.metric("授業給", f"¥{class_salary:,}")
    col3.metric("交通費・手当", f"¥{transport_fee + allowance:,}")

    st.write("**詳細データ**")
    display_df = pd.DataFrame([selected_row]).drop(columns=['年月'], errors='ignore')
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    st.divider()

    # --- 📄 給与明細PDFのダウンロード ---
    st.subheader("📄 給与明細のダウンロード")
    row_dict = selected_row.to_dict()
    
    try:
        pdf_bytes = generate_payslip_pdf(row_dict, selected_month)
        st.download_button(
            label=f"📥 {selected_month} の給与明細 (PDF) をダウンロード",
            data=pdf_bytes,
            file_name=f"給与明細_{selected_month}_{teacher_name}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception as e:
        st.error(f"⚠️ PDFの作成中にエラーが発生しました: {e}")