import time
import random
import logging
import streamlit as st
import pandas as pd

# 内部のログ出力用設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def robust_api_call(func, *args, retries=5, base_delay=2.0, fallback_value=None, notify=True, **kwargs):
    """
    外部通信のエラーを防ぎつつ、失敗した場合はその「原因」を画面に表示し、
    長期待機時にはユーザーを安心させるスピナーを表示する【極限防衛版】
    """
    func_name = getattr(func, '__name__', 'データ通信')
    
    for attempt in range(retries):
        try:
            # 関数の実行を試みる（成功すればすぐ返す！）
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # --- 🌟 強化ポイント1: エラーの種類によって「待つ時間」を賢く変える ---
            
            # パターンA: 429エラー (Google APIの制限「1分間に〇回まで」に引っかかった場合)
            if "429" in error_msg or "quota" in error_msg or "too many requests" in error_msg:
                # APIの制限リセットを待つため、長め（約15〜20秒）に待機して確実に通す
                sleep_time = 15.0 + random.uniform(2.0, 5.0)
                logger.warning(f"⚠️ [API制限] {func_name} でGoogleの制限を検知。{sleep_time:.1f}秒じっくり待機します...")
            
            # パターンB: 500系エラー (Google側のサーバーが一時的にダウン・混雑している場合)
            elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
                # 徐々に待つ時間を長くしていく (2秒 → 4秒 → 8秒...)
                sleep_time = base_delay * (2 ** attempt) + random.uniform(1.0, 3.0)
                logger.warning(f"⚠️ [サーバー混雑] {func_name} でGoogle側が混雑中。{sleep_time:.1f}秒後に再試行します...")
                
            # パターンC: それ以外のネットワークエラー（Wi-Fiの瞬断など）
            else:
                sleep_time = base_delay * (1.5 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"⚠️ [通信エラー] {func_name} でエラー発生。{sleep_time:.1f}秒後に再試行します...")

            # --- 🌟 強化ポイント2: 画面フリーズを防ぐスピナー付きリトライ実行 ---
            if attempt < retries - 1:
                # ユーザーへの通知ON（notify=True）の場合、画面のど真ん中にローディングを表示！
                if notify:
                    with st.spinner(f"📡 サーバー混雑を回避中... 自動で再接続します（約 {int(sleep_time)}秒お待ちください）"):
                        time.sleep(sleep_time)
                else:
                    # 通知OFF（裏側の完全なバックグラウンド処理）の場合はそのまま待機
                    time.sleep(sleep_time)
                
            # --- 🌟 強化ポイント3: 限界まで頑張ってダメだった場合の安全確保 ---
            else:
                logger.error(f"🚨 {func_name} が最大再試行回数({retries}回)に達しました。 | エラー: {e}")
                
                if notify:
                    st.error(f"🚨 【致命的な通信エラー】 `{func_name}` のデータ取得に失敗しました。\n\n**考えられる原因:** サーバーが大変混雑しているか、Googleの利用制限に達しています。1分ほど時間をおいてから再度お試しください。\n\n`システムエラー情報: {e}`")
                
                # エラーであることをダッシュボード側でも検知できるように、特殊なDataFrameを返す
                if isinstance(fallback_value, pd.DataFrame):
                    return pd.DataFrame({"APIエラー発生": [f"通信失敗: {e}"]})
                
                return fallback_value