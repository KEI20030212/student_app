import streamlit as st
import pandas as pd
import datetime 
import time  

from utils.api_guard import robust_api_call
# 🌟 変更: load_salary_data を新しくインポートに追加！
from utils.g_sheets import load_billing_data, load_fixed_costs, get_all_logs, load_salary_data

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
@st.cache_data(ttl=60, show_spinner=False)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner="☁️ 月謝（売上）データを取得中...")
def fetch_billing_data_cached(month):
    """月謝（売上）データを取得・キャッシュ・防御"""
    return robust_api_call(load_billing_data, month, fallback_value=pd.DataFrame())

@st.cache_data(ttl=3600, show_spinner="☁️ 固定費データを取得中...")
def fetch_fixed_costs_cached():
    """固定費データを取得・キャッシュ・防御"""
    return robust_api_call(load_fixed_costs, fallback_value=pd.DataFrame())

# 🌟 追加: 給与データを取得する爆速キャッシュ関数
@st.cache_data(ttl=600, show_spinner="☁️ 給与データを取得中...")
def fetch_salary_data_cached(month):
    """給与データを取得・キャッシュ・防御"""
    return robust_api_call(load_salary_data, month, fallback_value=pd.DataFrame())


def render_profit_loss_dashboard_page():
    st.header("📈 経営ダッシュボード (純利益管理)")
    
    # --- 動的に年月リストを生成する ---
    month_options = ["データなし"]
    df_all_logs = cached_get_all_logs()
    
    if not df_all_logs.empty and "APIエラー発生" not in df_all_logs.columns and '日時' in df_all_logs.columns:
        df_all_logs['日時'] = pd.to_datetime(df_all_logs['日時'], format='mixed', errors='coerce')
        valid_dates = df_all_logs.dropna(subset=['日時'])
        if not valid_dates.empty:
            valid_dates['年月'] = valid_dates['日時'].dt.strftime("%Y年%m月")
            month_options = sorted(valid_dates['年月'].unique().tolist(), reverse=True)
    
    if month_options == ["データなし"]:
        today = datetime.datetime.now()
        month_options = []
        for i in range(12):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            month_options.append(f"{y}年{m:02d}月")
        
    # 🌟 操作パネル
    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        month = st.selectbox("📅 集計月", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            with st.spinner("🔄 サーバーから最新データを取得中..."):
                time.sleep(0.6)  
                st.cache_data.clear()
            st.rerun()

    st.divider()

    if month == "データなし":
        st.info("集計対象のデータがありません。")
        return

    # ==========================================
    # 📊 データ取得とエラーハンドリング
    # ==========================================
    
    # 1. 売上の取得
    billing_df = fetch_billing_data_cached(month)
    
    total_revenue = 0
    if billing_df.empty:
        st.warning(f"⚠️ {month} の売上データがありません。「月謝管理」でまだ保存されていないか、通信エラーの可能性があります。上の更新ボタンをお試しください。")
    elif "💴 今月の請求額 (円)" in billing_df.columns:
        total_revenue = int(pd.to_numeric(billing_df["💴 今月の請求額 (円)"], errors='coerce').fillna(0).sum())

    # 2. 支出（給与）の取得 🌟 (給与ダッシュボードから全自動連携！)
    salary_df = fetch_salary_data_cached(month)
    
    total_salary = 0
    if salary_df.empty:
        st.info(f"💡 {month} の給与データがまだ「公開」されていません。給与ダッシュボードで公開ボタンを押すとここに反映されます。")
    elif "💰 最終支給額 (円)" in salary_df.columns:
        total_salary = int(pd.to_numeric(salary_df["💰 最終支給額 (円)"], errors='coerce').fillna(0).sum())

    # 3. 支出（固定費）の取得
    fixed_df = fetch_fixed_costs_cached()
    
    total_fixed = 0
    if fixed_df.empty:
        st.info("💡 固定費データが登録されていないか、取得できませんでした。")
    elif "金額" in fixed_df.columns:
        total_fixed = int(pd.to_numeric(fixed_df["金額"], errors='coerce').fillna(0).sum())

    # 4. 利益計算
    total_expense = total_salary + total_fixed
    net_profit = total_revenue - total_expense

    # ==========================================
    # 🖥️ 画面表示セクション
    # ==========================================
    
    # 🌟 上部：重要指標（KPI）サマリー
    c1, c2, c3 = st.columns(3)
    c1.metric("総売上", f"{total_revenue:,}円")
    c2.metric("総支出", f"{total_expense:,}円", delta=f"-{total_expense:,}", delta_color="inverse")
    c3.metric("純利益", f"{net_profit:,}円")

    st.divider() 

    # 🌟 中部：グラフと損益計算書（P&L）を左右に並べる
    col_chart, col_pnl = st.columns([1, 1])

    with col_chart:
        st.subheader("📊 収支バランス")
        st.bar_chart(pd.DataFrame({
            "カテゴリ": ["売上", "給与支出", "固定費", "純利益"],
            "金額": [total_revenue, -total_salary, -total_fixed, net_profit]
        }).set_index("カテゴリ"))

    with col_pnl:
        st.subheader("📋 損益計算書 (P&L)")
        
        pnl_data = [
            {"科目": "【売上高】", "金額 (円)": ""},
            {"科目": "　授業料等売上", "金額 (円)": f"{total_revenue:,}"},
            {"科目": "【経費】", "金額 (円)": ""},
            {"科目": "　講師給与手当", "金額 (円)": f"{total_salary:,}"},
            {"科目": "　固定費・その他経費", "金額 (円)": f"{total_fixed:,}"},
            {"科目": "【経費合計】", "金額 (円)": f"{total_expense:,}"},
            {"科目": "【営業利益】 (純利益)", "金額 (円)": f"{net_profit:,}"}
        ]
        st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)

    # 🌟 下部：各データの内訳をドリルダウン (3列に拡張！)
    st.divider()
    st.subheader("🔍 経費・売上の詳細内訳")
    
    col_detail1, col_detail2, col_detail3 = st.columns(3)
    
    with col_detail1:
        st.markdown("**💸 固定費一覧**")
        if not fixed_df.empty:
            st.dataframe(fixed_df, hide_index=True, use_container_width=True)
        else:
            st.info("データなし")
            
    with col_detail2:
        st.markdown("**👨‍🏫 講師給与一覧**")
        if not salary_df.empty:
            # 見やすいように講師名と支給額だけをピックアップして表示
            display_cols = [col for col in ["👨‍🏫 担当講師", "💰 最終支給額 (円)"] if col in salary_df.columns]
            st.dataframe(salary_df[display_cols] if display_cols else salary_df, hide_index=True, use_container_width=True)
        else:
            st.info("データなし")

    with col_detail3:
        st.markdown("**💴 売上（生徒別 月謝）一覧**")
        if not billing_df.empty:
            display_cols = [col for col in ["👤 生徒名", "生徒名", "💴 今月の請求額 (円)"] if col in billing_df.columns]
            st.dataframe(billing_df[display_cols] if display_cols else billing_df, hide_index=True, use_container_width=True) 
        else:
            st.info("データなし")