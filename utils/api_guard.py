import time
import random
import logging
import streamlit as st
import pandas as pd

# 内部のログ出力用設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def robust_api_call(func, *args, retries=4, base_delay=1.5, fallback_value=None, notify=True, **kwargs):
    """
    外部通信のエラーを防ぎつつ、失敗した場合はその「原因」を画面に表示する強化版
    """
    func_name = getattr(func, '__name__', 'データ通信')
    
    for attempt in range(retries):
        try:
            # 関数の実行を試みる
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            # 最後の試行以外なら、待機して再挑戦
            if attempt < retries - 1:
                # ジッター（ランダムな揺らぎ）を入れてリクエストを分散
                sleep_time = base_delay * (1.5 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"⚠️ {func_name} でエラー発生。{sleep_time:.2f}秒後に再試行します ({attempt+1}/{retries}) | エラー詳細: {e}")
                time.sleep(sleep_time)
                
            # 規定回数すべて失敗した場合
            else:
                logger.error(f"🚨 {func_name} が最大再試行回数に達しました。 | エラー詳細: {e}")
                
                if notify:
                    # 🌟 強化ポイント: トースト（右下の小さい通知）ではなく、画面に直接赤いエラーを出す！
                    st.error(f"🚨 【通信エラー】 `{func_name}` のデータ取得に失敗しました。\n\n**原因:** {e}")
                
                # エラーであることをダッシュボード側でも検知できるように、特殊なDataFrameを返す
                if isinstance(fallback_value, pd.DataFrame):
                    return pd.DataFrame({"APIエラー発生": [f"通信失敗: {e}"]})
                
                return fallback_value