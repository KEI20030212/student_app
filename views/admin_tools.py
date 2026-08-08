import streamlit as st
import time
from utils.g_sheets import batch_promote_students
from utils.api_guard import robust_api_call

def render_admin_tools_page():
    st.header("⚙️ 教室長用 管理ツール")
    
    # 🌟 権限チェック：教室長や管理者以外には見せない！
    if st.session_state.get('role') not in ['admin', 'owner', 'head_teacher']:
        st.error("アクセス権限がありません。このページは教室長専用です。")
        return

    st.subheader("🌸 新年度 一括進級処理")
    st.warning("⚠️ **注意：この操作は年に1回（3月末〜4月）だけ実行してください！**\n\n"
               "登録されている全生徒の学年を1つ上に自動で書き換えます。（例：中3 → 高1、高3 → 卒業）")
    
    with st.expander("👉 進級のルール（クリックで確認）"):
        st.write("""
        * 小1〜小5 → 1つ上の学年へ
        * 小6 → 中1
        * 中1〜中2 → 1つ上の学年へ
        * 中3 → 高1
        * 高1〜高2 → 1つ上の学年へ
        * 高3 → 卒業
        * ※「浪人」や「未設定」などの特殊な学年はそのまま残ります。（必要に応じて個別プロフィールの編集から手動で修正してください）
        """)

    # 間違えて押さないようにチェックボックスでロックをかける
    confirm = st.checkbox("上記の内容を理解し、全生徒の学年を更新することに同意します")
    
    if confirm:
        if st.button("🚀 一括進級を実行する", type="primary", use_container_width=True):
            with st.spinner("🌸 魔法をかけています（スプレッドシートを書き換え中...）"):
                success, message = robust_api_call(batch_promote_students, fallback_value=(False, "通信エラーが発生しました"))
                
                if success:
                    st.cache_data.clear() # キャッシュを消して最新状態にする
                    st.success(f"✅ 成功: {message}")
                    st.balloons() # 🎉 お祝いの風船を飛ばす！
                else:
                    st.error(f"❌ 失敗: {message}")