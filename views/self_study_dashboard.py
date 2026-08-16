import streamlit as st
import requests
import base64
import pandas as pd
import datetime
import time # 🌟 追加：待ち時間を作るためのモジュール

# 🌟 変更：新しく作った update_self_study_dashboard_date 関数を読み込む
from utils.g_sheets import load_self_study_data, update_self_study_dashboard_date
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
    
    col1, col2 = st.columns(2)
    target_branch = col1.radio(
        "🏢 校舎を選択", 
        ["田端新町校", "東十条校"], 
        horizontal=True
    )
    target_grade = col2.radio(
        "🏫 学年を選択", 
        ["小学生", "中学生", "高校生"], 
        horizontal=True
    )

    # 🌟 追加：年月の選択UI（デフォルトは今の年月）
    st.markdown("##### 📅 集計する月を設定")
    col_y, col_m = st.columns(2)
    current_year = datetime.date.today().year
    current_month = datetime.date.today().month
    selected_year = col_y.number_input("年 (C1セルに反映)", min_value=2020, max_value=2050, value=current_year)
    selected_month = col_m.number_input("月 (D1セルに反映)", min_value=1, max_value=12, value=current_month)

    # ==========================================
    # 🌟 ① 画像を引っ張るための「GASのURL」
    # ==========================================
    GAS_URLS = {
        "田端新町校": {
            "小学生": "https://script.google.com/macros/s/AKfycbxmaI040Qm0iDYykcP14JWw-eID_jeh_2oauTpW6ysYtYkdamtgn4uMLDYts72AQ71s/exec",
            "中学生": "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec",
            "高校生": "https://script.google.com/macros/s/AKfycbxEXhITzJWJrW7P_LdI1tEzFFm8p3YwoEUQ5u_-ZGmQj_GzV3dCbRJRk4a8v2SeEBgz/exec"
        },
        "東十条校": {
            "小学生": "https://script.google.com/macros/s/AKfycbzzCAbe8J24XICaGNR57qD9ui_yO7Dc2D-SrZxTxRiVU77YMM0xvGC7eO0wpHxhC5IF/exec",
            "中学生": "https://script.google.com/macros/s/AKfycbybDCaLgbVei66H7XdQgCaALoA0s1k-4lLuuIaESdRN5AYAwoROTLnJCU4bbp-wBhvf/exec",
            "高校生": "https://script.google.com/macros/s/AKfycbz-_v6lPKqWQUpzMiZ8ExrwY722jmAbfI2Xmf2J6Lz0Z2S6HPx50KIoZMAth7lk8DEVKA/exec"
        }
    }
    
    # ==========================================
    # 🌟 ② セル(C1, D1)に直接書き込むための「スプレッドシートID」
    # ==========================================
    SHEET_IDS = {
        "田端新町校": {
            "小学生": "1V4ID3wirXoTM3M-rdZeYhfu0wrVE19wu3AZOod2XVJ0",
            "中学生": "1Tbbz7SO0-chcOlUwsDjTVhAYQ9zXNhopfwSPFpByD9A",
            "高校生": "1nnFJo8k81VBuz232gAZYVnSX47YgLuaU8Mqt1hzuS_M"
        },
        "東十条校": {
            "小学生": "1n0NvREF5Sf8WHMVOXXHCfm6EhsYDtcDd0qB4dXMR4c8",
            "中学生": "1okTYoVDhBfZzjcq5bVBeMxqc-7Ocv1Woz4JISDI3vGQ",
            "高校生": "12fWkakGZPt8it_OxZNmddDOimzM0CTmCrD2GS5mIX2U"
        }
    }
    
    GAS_URL = GAS_URLS[target_branch].get(target_grade)
    target_sheet_id = SHEET_IDS[target_branch].get(target_grade)
    SECRET_KEY = "juku-graph-2026"
    
    if not GAS_URL or GAS_URL.startswith("ここ") or not target_sheet_id or target_sheet_id.startswith("ここ"):
        st.warning(f"⚠️ 【{target_branch} - {target_grade}】用の設定が未完了です。コードのURLまたはスプレッドシートIDを書き換えてください。")
        return
        
    if st.button(f"🚀 【{target_branch} - {target_grade}】の {selected_month}月 のグラフ画像を取得する", type="primary", use_container_width=True):
        
        # 🌟 処理1：スプレッドシートの年月を書き換える
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
                st.stop() # 失敗したらここで処理をストップ
                
            # 🌟 超重要：Google側が新しい月でグラフを「描き直す」まで3秒待ってあげる
            time.sleep(3)
        
        # 🌟 処理2：書き換わって完成した最新グラフを引っ張ってくる
        with st.spinner(f"最新のグラフ画像を引っ張っています...（最大1分ほどかかる場合があります）"):
            try:
                response = requests.get(f"{GAS_URL}?key={SECRET_KEY}", timeout=60)
                
                if response.status_code == 200:
                    result_text = response.text
                    
                    if result_text == "認証エラー" or "エラー" in result_text or result_text == "グラフが見つかりません":
                        st.error(f"❌ 画像の取得に失敗しました: {result_text}")
                    else:
                        image_bytes = base64.b64decode(result_text)
                        
                        st.success(f"✅ 【{target_branch} - {target_grade}】の {selected_month}月分 のグラフ取得に成功しました！")
                        
                        with st.container(border=True):
                            st.image(image_bytes, use_container_width=True)
                        
                        st.download_button(
                            label=f"📥 このグラフ画像をダウンロードする（PNG形式）",
                            data=image_bytes,
                            file_name=f"学習時間グラフ_{target_branch}_{target_grade}_{selected_year}年{selected_month}月.png",
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )
                else:
                    st.error(f"通信エラーが発生しました。（ステータスコード: {response.status_code}）")
            except requests.exceptions.Timeout:
                st.error("❌ 画像の生成に時間がかかりすぎています。スプレッドシートのデータ量が多すぎるか、Googleのサーバーが混雑している可能性があります。")
            except Exception as e:
                st.error(f"システムエラー: {str(e)}")