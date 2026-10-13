# views/self_study_dashboard.py

import streamlit as st
import requests
import base64
import pandas as pd
import datetime
import time 

# 🌟 NEW: configからURLとIDを呼び出す
from utils.config import SELF_STUDY_GAS_URLS, SELF_STUDY_SHEET_IDS, SELF_STUDY_SECRET_KEY

from utils.g_sheets import (
    load_self_study_data, 
    update_self_study_dashboard_date,
    load_system_settings # 🌟 NEW: 動的な校舎名取得用
)
from utils.api_guard import robust_api_call

def render_self_study_dashboard():
    st.header("📊 学習時間ダッシュボード")
    
    st.write("スプレッドシート側で作成・デザインされた最新のグラフを、安全に画像としてダウンロードできます✨")
    st.caption("※スプレッドシート側でグラフの色やタイトルを変更すると、次に取得した時に即座に反映されます。")
    
    st.divider()

    # ==========================================
    # 🚨 追加機能：自習・足遠のきアラート
    # ==========================================
    st.subheader("🚨 自習室・足遠のきアラート")
    st.write("先月はよく自習に来ていたのに、直近1週間ぱったりと来なくなった生徒を自動検知します。")

    with st.spinner("自習記録を分析して、退塾予兆のある生徒を探しています..."):
        df_ss = robust_api_call(load_self_study_data, fallback_value=pd.DataFrame())
        
        if df_ss.empty or 'APIエラー発生' in df_ss.columns:
            st.info("自習データが取得できないため、アラート分析をスキップしました。")
        else:
            df_ss['日付'] = pd.to_datetime(df_ss['日付'], errors='coerce')
            df_ss = df_ss.dropna(subset=['日付'])
            
            today = pd.Timestamp.today().normalize()
            recent_start = today - pd.Timedelta(days=7)
            past_start = recent_start - pd.Timedelta(days=28) 
            
            df_past = df_ss[(df_ss['日付'] >= past_start) & (df_ss['日付'] < recent_start)]
            df_recent = df_ss[df_ss['日付'] >= recent_start]
            
            name_col = '名前' if '名前' in df_ss.columns else ('生徒名' if '生徒名' in df_ss.columns else None)
            
            if name_col:
                past_counts = df_past.groupby(name_col).size()
                recent_counts = df_recent.groupby(name_col).size()
                
                alerts = []
                for student, p_count in past_counts.items():
                    if p_count >= 4:
                        r_count = recent_counts.get(student, 0)
                        if r_count == 0:
                            avg_per_week = p_count / 4
                            alerts.append({
                                "生徒名": student,
                                "先月のペース": f"週 {avg_per_week:.1f} 回",
                                "直近7日間の来校": "🚨 0 回"
                            })
                
                if alerts:
                    st.error("⚠️ **以下の生徒の足が遠のいています！次回の授業時などに必ず声かけ（ヒアリング）を行ってください。**")
                    df_alerts = pd.DataFrame(alerts)
                    df_alerts.index = df_alerts.index + 1
                    st.table(df_alerts)
                else:
                    st.success("✨ 現在、急に足が遠のいた生徒はいません。自習室の利用ペースは安定しています！")
            else:
                st.info("データ内に「名前」列が見つからないため分析できません。")

    st.divider()

    # ==========================================
    # 📊 既存機能：グラフ画像ダウンロード
    # ==========================================
    st.subheader("📥 グラフ画像のダウンロード")
    
    # 🌟 NEW: load_system_settings() を使って校舎リストを動的に構築
    settings = robust_api_call(load_system_settings, fallback_value={})
    saved_branches_str = settings.get("メイン校舎名", "")
    
    # "田端新町校:t, 東十条駅前校:h" をパースして校舎名だけのリストにする
    branch_list = []
    if saved_branches_str:
        for b in saved_branches_str.split(','):
            if ':' in b:
                branch_list.append(b.split(':')[0].strip())
                
    # もし何らかの理由で取得できなかった場合のフェイルセーフ
    if not branch_list:
        branch_list = ["その他"]

    col1, col2 = st.columns(2)
    target_branch = col1.radio(
        "🏢 校舎を選択", 
        branch_list, # 🌟 動的に取得したリストを使う
        horizontal=True
    )
    target_grade = col2.radio(
        "🏫 学年を選択", 
        ["小学生", "中学生", "高校生"], 
        horizontal=True
    )

    st.markdown("##### 📅 集計する月を設定")
    col_y, col_m = st.columns(2)
    current_year = datetime.date.today().year
    current_month = datetime.date.today().month
    selected_year = col_y.number_input("年 (C1セルに反映)", min_value=2020, max_value=2050, value=current_year)
    selected_month = col_m.number_input("月 (D1セルに反映)", min_value=1, max_value=12, value=current_month)

    # 🌟 config.pyからデータを取得
    GAS_URL = SELF_STUDY_GAS_URLS.get(target_branch, {}).get(target_grade)
    target_sheet_id = SELF_STUDY_SHEET_IDS.get(target_branch, {}).get(target_grade)
    
    if not GAS_URL or not target_sheet_id:
        st.warning(f"⚠️ 【{target_branch} {target_grade}】用のグラフ連携設定が config.py に未登録です。")
        return

    def display_safe_image_download_link(img_bytes, filename, color="#1E90FF"):
        b64_img = base64.b64encode(img_bytes).decode('utf-8')
        html_button = f'''
        <a href="data:image/png;base64,{b64_img}" download="{filename}" 
           style="display: block; text-align: center; padding: 10px 15px; background-color: {color}; 
                  color: white; text-decoration: none; border-radius: 8px; font-weight: bold; 
                  font-family: sans-serif; font-size: 16px; margin-top: 10px; transition: 0.3s;
                  border: 1px solid #104E8B;">
            📥 このグラフ画像をダウンロードする（PNG形式）
        </a>
        '''
        st.markdown(html_button, unsafe_allow_html=True)

    if st.button(f"🚀 【{target_branch} {target_grade}】の {selected_month}月 のグラフ画像を取得する", type="primary", use_container_width=True):
        
        with st.spinner(f"スプレッドシートを {selected_year}年 {selected_month}月 に設定しています..."):
            success, msg = robust_api_call(
                update_self_study_dashboard_date, 
                target_sheet_id, 
                selected_year, 
                selected_month, 
                fallback_value=(False, "通信エラー")
            )
            
            if not success:
                st.error(f"❌ スプレッドシートの日付更新に失敗しました: {msg}")
                st.stop()
                
            time.sleep(3)
        
        with st.spinner(f"最新のグラフ画像を引っ張っています...（最大1分ほどかかる場合があります）"):
            try:
                response = requests.get(f"{GAS_URL}?key={SELF_STUDY_SECRET_KEY}", timeout=60)
                
                if response.status_code == 200:
                    result_text = response.text
                    
                    if result_text == "認証エラー" or "エラー" in result_text or result_text == "グラフが見つかりません":
                        st.error(f"❌ 画像の取得に失敗しました: {result_text}")
                    else:
                        image_bytes = base64.b64decode(result_text)
                        st.success(f"✅ 【{target_branch} {target_grade}】の {selected_month}月分 のグラフ取得に成功しました！")
                        
                        with st.container(border=True):
                            st.image(image_bytes, use_container_width=True)
                        
                        safe_file_name = f"学習時間グラフ_{target_branch}_{target_grade}_{selected_year}年{selected_month}月.png"
                        display_safe_image_download_link(image_bytes, safe_file_name)
                        
                else:
                    st.error(f"通信エラーが発生しました。（ステータスコード: {response.status_code}）")
            except requests.exceptions.Timeout:
                st.error("❌ 画像の生成に時間がかかりすぎています。スプレッドシートのデータ量が多すぎるか、Googleのサーバーが混雑している可能性があります。")
            except Exception as e:
                st.error(f"システムエラー: {str(e)}")