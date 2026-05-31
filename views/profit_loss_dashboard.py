import streamlit as st
import pandas as pd
import datetime 
import time  

from utils.api_guard import robust_api_call
from utils.g_sheets import load_billing_data, load_fixed_costs, get_all_logs, load_salary_data

# --- 🚀 データ取得を高速化＆保護するキャッシュ関数 ---
@st.cache_data(ttl=60, show_spinner=False)
def cached_get_all_logs():
    return robust_api_call(get_all_logs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def fetch_billing_data_cached(month):
    return robust_api_call(load_billing_data, month, fallback_value=pd.DataFrame())

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fixed_costs_cached():
    return robust_api_call(load_fixed_costs, fallback_value=pd.DataFrame())

@st.cache_data(ttl=600, show_spinner=False)
def fetch_salary_data_cached(month):
    return robust_api_call(load_salary_data, month, fallback_value=pd.DataFrame())


def render_profit_loss_dashboard_page():
    st.header("📈 経営ダッシュボード (損益・純利益管理)")
    st.write("各月の収支カルテに加え、中長期的な売上・人件費・純利益の推移を可視化します。")
    
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
        
    # 操作パネル
    col_month, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    
    with col_month:
        month = st.selectbox("📅 個別集計を行う月を選択", month_options)
        
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

    # 🌟 2つの視点にタブを分ける（単月詳細 vs 複数月トレンド）
    tab_single, tab_trend = st.tabs(["📊 単月損益カルテ (P&L)", "📈 中長期売上・純利益推移"])

    # 固定費の取得（全機能共通）
    fixed_df = fetch_fixed_costs_cached()
    total_fixed = 0
    if not fixed_df.empty and "金額" in fixed_df.columns:
        total_fixed = int(pd.to_numeric(fixed_df["金額"], errors='coerce').fillna(0).sum())

    # ==========================================
    # 🌟 タブ1：単月損益カルテ (P&L)
    # ==========================================
    with tab_single:
        # 売上の取得
        billing_df = fetch_billing_data_cached(month)
        total_revenue = 0
        if billing_df.empty:
            st.warning(f"⚠️ {month} の売上データがありません。月謝管理画面での保存状況を確認してください。")
        elif "💴 今月の請求額 (円)" in billing_df.columns:
            total_revenue = int(pd.to_numeric(billing_df["💴 今月の請求額 (円)"], errors='coerce').fillna(0).sum())

        # 支出（給与）の取得
        salary_df = fetch_salary_data_cached(month)
        total_salary = 0
        if salary_df.empty:
            st.info(f"💡 {month} の給与データがまだ「公開」されていません。給与ダッシュボードで公開すると反映されます。")
        elif "💰 最終支給額 (円)" in salary_df.columns:
            total_salary = int(pd.to_numeric(salary_df["💰 最終支給額 (円)"], errors='coerce').fillna(0).sum())

        total_expense = total_salary + total_fixed
        net_profit = total_revenue - total_expense

        # 重要指標（KPI）サマリー
        c1, c2, c3 = st.columns(3)
        c1.metric("総売上", f"{total_revenue:,}円")
        c2.metric("総支出", f"{total_expense:,}円", delta=f"-{total_expense:,}", delta_color="inverse")
        
        # 利益率（労働分配率）の計算
        salary_rate = (total_salary / total_revenue * 100) if total_revenue > 0 else 0
        
        # 純利益の表示と危険判定
        if net_profit > 0:
            c3.metric("純利益", f"{net_profit:,}円")
        else:
            c3.metric("純利益（赤字）", f"{net_profit:,}円", delta="要コスト改善", delta_color="inverse")

        st.divider() 

        col_chart, col_pnl = st.columns([1, 1])
        with col_chart:
            st.markdown(f"##### 📊 {month} の収支比率")
            st.bar_chart(pd.DataFrame({
                "カテゴリ": ["売上", "給与支出", "固定費", "純利益"],
                "金額": [total_revenue, -total_salary, -total_fixed, net_profit]
            }).set_index("カテゴリ"))
            
            # 人件費率のアラート表示
            st.markdown(f"**💡 経営指標チェック:**\n\n人件費率（労働分配率）: **{salary_rate:.1f}%**")
            if salary_rate > 50:
                st.error("⚠️ 人件費率が50%を超えています。コマ数の最適化、または1:2、1:3の授業形態の割合を増やすことを検討してください。")
            elif salary_rate > 35:
                st.success("🟢 健全な人件費水準です。このバランスを維持しましょう。")
            elif salary_rate > 0:
                st.warning("👀 人件費率がかなり低めです。授業の稼働に対して単価が適切か、または売上過多になっていないか確認してください。")

        with col_pnl:
            st.markdown("##### 📋 損益計算書 (P&L)")
            pnl_data = [
                {"科目": "【売上高】", "金額 (円)": ""},
                {"科目": "　授業料等売上", "金額 (円)": f"{total_revenue:,}"},
                {"科目": "【経費】", "金額 (円)": ""},
                {"科目": "　講師給与手当（変動費）", "金額 (円)": f"{total_salary:,}"},
                {"科目": "　固定費・その他経費", "金額 (円)": f"{total_fixed:,}"},
                {"科目": "【経費合計】", "金額 (円)": f"{total_expense:,}"},
                {"科目": "【営業利益】 (純利益)", "金額 (円)": f"{net_profit:,}"}
            ]
            st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)

        st.divider()
        st.write("##### 🔍 各種データの詳細内訳")
        col_detail1, col_detail2, col_detail3 = st.columns(3)
        
        with col_detail1:
            st.markdown("**💸 固定費一覧**")
            st.dataframe(fixed_df, hide_index=True, use_container_width=True) if not fixed_df.empty else st.info("データなし")
                
        with col_detail2:
            st.markdown("**👨‍🏫 講師給与一覧**")
            if not salary_df.empty:
                display_cols = [col for col in ["👨‍🏫 担当講師", "💰 最終支給額 (円)"] if col in salary_df.columns]
                st.dataframe(salary_df[display_cols] if display_cols else salary_df, hide_index=True, use_container_width=True)
            else:
                st.info("データなし")

        with col_detail3:
            st.markdown("**🔑 売上（生徒別 月謝）一覧**")
            if not billing_df.empty:
                display_cols = [col for col in ["👤 生徒名", "生徒名", "💴 今月の請求額 (円)"] if col in billing_df.columns]
                st.dataframe(billing_df[display_cols] if display_cols else billing_df, hide_index=True, use_container_width=True) 
            else:
                st.info("データなし")

    # ==========================================
    # 🌟 タブ2：中長期売上・純利益推移（新設機能）
    # ==========================================
    with tab_trend:
        st.subheader("📈 時系列トレンド分析")
        st.write("過去から現在までの売上高・人件費支出・純利益の推移を横断集計し、教室の成長度を可視化します。")
        
        # 直近から最大6ヶ月分のデータをバックグラウンドで一括走査して結合する
        trend_months = month_options[:6][::-1] # 古い月順に並び替え
        
        trend_data = []
        
        with st.status("📊 複数月の財務データを集計・解析中...", expanded=False) as status:
            for m_str in trend_months:
                # 各月の売上データをスキャン
                b_df = robust_api_call(load_billing_data, m_str, fallback_value=pd.DataFrame())
                m_rev = 0
                if not b_df.empty and "💴 今月の請求額 (円)" in b_df.columns:
                    m_rev = int(pd.to_numeric(b_df["💴 今月の請求額 (円)"], errors='coerce').fillna(0).sum())
                
                # 各月の給与データをスキャン
                s_df = robust_api_call(load_salary_data, m_str, fallback_value=pd.DataFrame())
                m_sal = 0
                if not s_df.empty and "💰 最終支給額 (円)" in s_df.columns:
                    m_sal = int(pd.to_numeric(s_df["💰 最終支給額 (円)"], errors='coerce').fillna(0).sum())
                
                m_exp = m_sal + total_fixed
                m_prof = m_rev - m_exp
                
                trend_data.append({
                    "年月": m_str,
                    "総売上高": m_rev,
                    "人件費": m_sal,
                    "総経費": m_exp,
                    "純利益": m_prof
                })
            status.update(label="集計完了！", state="complete")
            
        if trend_data:
            df_trends = pd.DataFrame(trend_data)
            
            # グラフ用のデータフレームに加工
            df_chart = df_trends.set_index("年月")[["総売上高", "総経費", "純利益"]]
            
            st.markdown("##### 📈 収支・純利益推移ライングラフ")
            st.line_chart(df_chart, use_container_width=True)
            
            st.markdown("##### 📊 経費構造の月別比較（積層棒グラフ）")
            # 経費の内訳を比較しやすいように加工
            df_expense_chart = df_trends.set_index("年月")[["人件費"]]
            df_expense_chart["固定費"] = total_fixed
            st.bar_chart(df_expense_chart, use_container_width=True)
            
            st.markdown("##### 📋 財務推移データ一覧")
            st.dataframe(df_trends[["年月", "総売上高", "人件費", "総経費", "純利益"]].sort_values("年月", ascending=False), hide_index=True, use_container_width=True)