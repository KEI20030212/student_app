import streamlit as st
import requests
import base64
import pandas as pd
import datetime

from utils.g_sheets import load_self_study_data
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
            # 日付データとして正確に処理
            df_ss['日付'] = pd.to_datetime(df_ss['日付'], errors='coerce')
            df_ss = df_ss.dropna(subset=['日付'])
            
            # 日数の定義（今日、7日前、35日前）
            today = pd.Timestamp.today().normalize()
            recent_start = today - pd.Timedelta(days=7)
            past_start = recent_start - pd.Timedelta(days=28) # 過去4週間
            
            # 期間ごとにデータを分割
            df_past = df_ss[(df_ss['日付'] >= past_start) & (df_ss['日付'] < recent_start)]
            df_recent = df_ss[df_ss['日付'] >= recent_start]
            
            # 生徒ごとの来店回数をカウント（列名が「名前」か「生徒名」かを確認）
            name_col = '名前' if '名前' in df_ss.columns else ('生徒名' if '生徒名' in df_ss.columns else None)
            
            if name_col:
                past_counts = df_past.groupby(name_col).size()
                recent_counts = df_recent.groupby(name_col).size()
                
                alerts = []
                for student, p_count in past_counts.items():
                    # 💡 条件：過去4週間で「4回以上（平均週1以上）」来ていた生徒を対象とする
                    if p_count >= 4:
                        r_count = recent_counts.get(student, 0)
                        # 💡 条件：直近7日間は「0回」しか来ていない
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
                    # インデックスを1からにする
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
    target_grade = st.radio(
        "🏫 グラフを取得する対象（スプレッドシート）を選択してください", 
        ["小学生", "中学生", "高校生"], 
        horizontal=True
    )

    GAS_URLS = {
        "小学生": "https://script.google.com/macros/s/AKfycbxmaI040Qm0iDYykcP14JWw-eID_jeh_2oauTpW6ysYtYkdamtgn4uMLDYts72AQ71s/exec",
        "中学生": "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec",
        "高校生": "https://script.google.com/macros/s/AKfycbxEXhITzJWJrW7P_LdI1tEzFFm8p3YwoEUQ5u_-ZGmQj_GzV3dCbRJRk4a8v2SeEBgz/exec"
    }
    
    GAS_URL = GAS_URLS.get(target_grade)
    SECRET_KEY = "juku-graph-2026"
    
    if not GAS_URL:
        st.error("システムエラー：URLが設定されていません。")
        return
        
    if st.button(f"🚀 【{target_grade}】の最新グラフ画像をスプレッドシートから取得する", type="primary", use_container_width=True):
        
        with st.spinner(f"【{target_grade}】のスプレッドシートからグラフを画像化して引っ張っています...（約3秒）"):
            try:
                response = requests.get(f"{GAS_URL}?key={SECRET_KEY}", timeout=60)
                
                if response.status_code == 200:
                    result_text = response.text
                    
                    if result_text == "認証エラー" or "エラー" in result_text or result_text == "グラフが見つかりません":
                        st.error(f"❌ 画像の取得に失敗しました: {result_text}")
                    else:
                        image_bytes = base64.b64decode(result_text)
                        
                        st.success(f"✅ 【{target_grade}】のグラフ画像の取得に成功しました！プレビューを確認してダウンロードしてください。")
                        
                        with st.container(border=True):
                            st.image(image_bytes, use_container_width=True)
                        
                        st.download_button(
                            label=f"📥 【{target_grade}】のグラフ画像をダウンロードする（PNG形式）",
                            data=image_bytes,
                            file_name=f"学習時間グラフ_{target_grade}.png",
                            mime="image/png",
                            type="primary",
                            use_container_width=True
                        )
                else:
                    st.error(f"通信エラーが発生しました。（ステータスコード: {response.status_code}）")
            except Exception as e:
                st.error(f"システムエラー: {str(e)}")