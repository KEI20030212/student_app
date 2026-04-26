import streamlit as st
import pandas as pd

# 🌟 共通の防御関数をインポート
from utils.api_guard import robust_api_call
from utils.g_sheets import load_published_salary
from utils.pdf_generator import generate_payslip_pdf

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
# 💡 スピナーのメッセージを追加してフリーズ感を解消
@st.cache_data(show_spinner="☁️ 給与データを取得中...")
def fetch_published_salary_cached():
    """公開済みの給与データを取得・キャッシュ・防御"""
    return robust_api_call(load_published_salary, fallback_value=pd.DataFrame())

def render_my_salary_page():
    # ログインしている先生の名前を取得
    teacher_name = st.session_state.get('username', '先生')
    
    st.header(f"💴 {teacher_name} 先生の給与確認")
    st.write("※教室長から公開された確定済みの給与明細を表示しています。")

    # 1. 公開された給与データを読み込む（キャッシュ＆防御経由で爆速！）
    df_all_salaries = fetch_published_salary_cached()
    
    # --------------------------------------------------------
    # 🌟 操作パネル（月選択 ＆ 更新ボタン）を画面上部に配置
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
            # このページ用のキャッシュだけをピンポイントでクリア
            fetch_published_salary_cached.clear()
            st.toast("最新データを取得します...", icon="⏳")
            st.rerun()

    st.divider()
    # --------------------------------------------------------

    # --- ⚠️ エラーハンドリング（ボタンの下に配置することで、エラー時も更新ボタンを押せるようにする） ---
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
    
    # 💡 数値計算時のエラー回避（空欄や文字列が混ざっていても安全に0として処理）
    def safe_int(val):
        try:
            return int(float(val))
        except:
            return 0

    final_salary = safe_int(selected_row.get('💰 最終支給額 (円)', 0))
    class_salary = safe_int(selected_row.get('授業給 (円)', 0))
    transport_fee = safe_int(selected_row.get('交通費合計 (円)', 0))
    allowance = safe_int(selected_row.get('役職手当 (円)', 0))

    # 4. 見やすいカード形式で表示
    st.markdown(f"### 📊 {selected_month} の給与概要")
    col1, col2, col3 = st.columns(3)
    col1.metric("最終支給額", f"¥{final_salary:,}")
    col2.metric("授業給", f"¥{class_salary:,}")
    col3.metric("交通費・手当", f"¥{transport_fee + allowance:,}")

    st.write("**詳細データ**")
    # 不要な「年月」列などを隠して綺麗にテーブル表示 (errors='ignore'で列がない場合のエラーを防ぐ)
    display_df = pd.DataFrame([selected_row]).drop(columns=['年月'], errors='ignore')
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    st.divider()

    # 5. 🌟 先生自身でPDFダウンロード！
    st.subheader("📄 給与明細のダウンロード")
    
    # PDF職人に渡すための辞書データに変換
    row_dict = selected_row.to_dict()
    
    try:
        # PDFを生成（教室長ページと同じ関数を使うのでデザインも同じ！）
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