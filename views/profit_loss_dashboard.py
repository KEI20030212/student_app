import streamlit as st
import pandas as pd
import datetime 
import time  # 🌟 ボタンのフィードバック用にtimeを追加

# 🌟 共通の防御関数をインポート
from utils.api_guard import robust_api_call
from utils.g_sheets import load_billing_data, load_fixed_costs

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
@st.cache_data(show_spinner="☁️ 月謝（売上）データを取得中...")
def fetch_billing_data_cached(month):
    """月謝（売上）データを取得・キャッシュ・防御"""
    return robust_api_call(load_billing_data, month, fallback_value=pd.DataFrame())

@st.cache_data(show_spinner="☁️ 固定費データを取得中...")
def fetch_fixed_costs_cached():
    """固定費データを取得・キャッシュ・防御"""
    return robust_api_call(load_fixed_costs, fallback_value=pd.DataFrame())

def render_profit_loss_dashboard_page():
    st.header("📈 経営ダッシュボード (純利益管理)")
    
    # --- 現在から過去12ヶ月分を動的に生成する ---
    today = datetime.datetime.now()
    month_options = []
    
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_options.append(f"{y}年{m:02d}月")
        
    # 🌟 操作パネル（月選択 ＆ 更新ボタン）を画面上部に横並びで配置
    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        month = st.selectbox("📅 集計月", month_options)
        
    with col_btn:
        if st.button("🔄 最新データに更新", type="primary", use_container_width=True):
            # 🌟 改善ポイント1: 「押した感」を出すために少しだけ待機時間をいれる
            with st.spinner("🔄 サーバーから最新データを取得中..."):
                time.sleep(0.6)  # アニメーションを確実に見せるための意図的なタメ
                fetch_billing_data_cached.clear()
                fetch_fixed_costs_cached.clear()
            st.rerun()

    st.divider()

    # ==========================================
    # 📊 データ取得とエラーハンドリング
    # ==========================================
    
    # 1. 売上の取得 (🌟 キャッシュ＆防御経由)
    billing_df = fetch_billing_data_cached(month)
    
    total_revenue = 0
    # 🌟 改善ポイント2: データが空だった場合に「なぜ表示されないか」をユーザーに明示する
    if billing_df.empty:
        st.warning(f"⚠️ {month} の売上データがありません。「月謝管理」でまだ保存されていないか、通信エラーの可能性があります。上の更新ボタンをお試しください。")
    elif "💴 今月の請求額 (円)" in billing_df.columns:
        total_revenue = int(pd.to_numeric(billing_df["💴 今月の請求額 (円)"], errors='coerce').fillna(0).sum())

    # 2. 支出（給与）の取得
    # 💡 TODO: salary_dashboardから保存された給与データを読み込むAPIが完成したら置き換え
    total_salary = 450000 # 仮のデータ

    # 3. 支出（固定費）の取得 (🌟 キャッシュ＆防御経由)
    fixed_df = fetch_fixed_costs_cached()
    
    total_fixed = 0
    if fixed_df.empty:
        st.info("💡 固定費データが登録されていないか、取得できませんでした。")
    elif "金額" in fixed_df.columns:
        # 空白や文字列が混ざっていてもエラーにならないように数値変換
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

    st.divider() # 区切り線

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
        
        # 損益計算書風のデータフレームを作成
        pnl_data = [
            {"科目": "【売上高】", "金額 (円)": ""},
            {"科目": "　授業料等売上", "金額 (円)": f"{total_revenue:,}"},
            {"科目": "【経費】", "金額 (円)": ""},
            {"科目": "　講師給与手当", "金額 (円)": f"{total_salary:,}"},
            {"科目": "　固定費・その他経費", "金額 (円)": f"{total_fixed:,}"},
            {"科目": "【経費合計】", "金額 (円)": f"{total_expense:,}"},
            {"科目": "【営業利益】 (純利益)", "金額 (円)": f"{net_profit:,}"}
        ]
        # hide_index=True でスッキリした表にする
        st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)

    # 🌟 下部：各データの内訳をドリルダウン
    st.divider()
    st.subheader("🔍 経費・売上の詳細内訳")
    
    col_detail1, col_detail2 = st.columns(2)
    
    with col_detail1:
        st.markdown("**💸 固定費一覧**")
        if not fixed_df.empty:
            st.dataframe(fixed_df, hide_index=True, use_container_width=True)
        else:
            st.info("表示できる固定費データがありません。")
            
    with col_detail2:
        st.markdown("**💴 売上（生徒別 月謝）一覧**")
        if not billing_df.empty:
            # カラムが存在するかチェックしてから表示する（エラー回避）
            display_cols = [col for col in ["👤 生徒名", "生徒名", "💴 今月の請求額 (円)"] if col in billing_df.columns]
            if display_cols:
                st.dataframe(billing_df[display_cols], hide_index=True, use_container_width=True)
            else:
                st.dataframe(billing_df, hide_index=True, use_container_width=True) 
        else:
            st.info("表示できる売上データがありません。")