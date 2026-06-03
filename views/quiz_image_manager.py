import streamlit as st
import pandas as pd
import datetime
import time
import io
from PIL import Image

from utils.g_sheets import get_student_master
from utils.g_drive import upload_image_to_drive, list_student_images
from utils.api_guard import robust_api_call

@st.cache_data(ttl=600)
def cached_get_student_master():
    return robust_api_call(get_student_master, fallback_value=pd.DataFrame())

def process_image_quality(file_bytes):
    """画質補正を行わず、最高画質（劣化なし）を維持してJPEGに統一する安全関数"""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')

        out_buf = io.BytesIO()
        # 🌟 画質劣化をゼロ（品質100%、色にじみなし）にして保存
        img.save(out_buf, format="JPEG", quality=100, subsampling=0)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        return file_bytes, None

def render_quiz_image_manager_page():
    st.header("📸 小テスト・画像管理")
    st.write("生徒の小テストの答案やノートの写真を、Google Driveへ高画質で保存・確認できます✨")

    df_students = cached_get_student_master()
    if df_students.empty:
        st.error("生徒データの取得に失敗しました。時間をおいて再読み込みしてください。")
        st.stop()

    student_options = (df_students['生徒ID'].astype(str) + " - " + df_students['生徒名']).tolist()
    selected_student = st.selectbox("👤 生徒を選択してください", student_options, index=None, placeholder="--選択--")

    if selected_student is None:
        st.info("👆 生徒を選択すると、画像のアップロードや過去の答案ギャラリーが開きます。")
        return

    student_id = selected_student.split(" - ")[0]
    student_name = selected_student.split(" - ")[1]

    st.divider()
    st.subheader(f"✍️ {student_name} さんの小テスト・ノート登録")

    st.info("💡 **アップロードのコツ:** スマホ標準のカメラアプリでピントを合わせて綺麗に撮影し、以下の枠からアップロードしてください。")

    # ファイルアップローダーのみのシンプルなUI
    uploaded_file = st.file_uploader("📂 写真ファイルを選択してください (JPG / PNG)", type=["jpg", "jpeg", "png"], key=f"file_{student_id}")

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type
        
        with st.spinner("✨ 画像を最高画質データに変換中..."):
            file_bytes, new_mime = process_image_quality(file_bytes)
            if new_mime:
                mime_type = new_mime
        
        now_date = datetime.date.today().strftime("%Y%m%d")
        
        with st.container(border=True):
            st.markdown("**🏷️ 保存するファイルの設定**")
            c_meta1, c_meta2 = st.columns(2)
            subj = c_meta1.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "その他"], key=f"meta_sub_{student_id}")
            title_suffix = c_meta2.text_input("補足名 (任意)", placeholder="単元名やテスト名（例: 二次関数）", key=f"meta_title_{student_id}")
            
            suffix_str = f"_{title_suffix}" if title_suffix.strip() else ""
            file_name = f"{now_date}_{subj}{suffix_str}.jpg"

            if st.button("🚀 この設定でGoogle Driveへ保存する", type="primary", use_container_width=True):
                with st.spinner(f"【{file_name}】をアップロード中..."):
                    success, result = robust_api_call(
                        upload_image_to_drive,
                        student_id=student_id,
                        student_name=student_name,
                        file_name=file_name,
                        file_bytes=file_bytes,
                        mime_type=mime_type,
                        fallback_value=(False, "タイムアウト")
                    )
                    
                    if success:
                        st.success(f"✅ 保存完了しました！LINEレポート機能にも自動でリンクが追加されます。")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ アップロードに失敗しました: {result}")

    # ==========================================
    # 🖼️ 過去の答案ギャラリー表示セクション
    # ==========================================
    st.divider()
    st.subheader("🖼️ 過去の画像ギャラリー")
    
    with st.spinner("Google Driveから画像履歴を読み込み中..."):
        images = robust_api_call(list_student_images, student_id, student_name, fallback_value=[])

    if not images:
        st.info("まだこの生徒のフォルダに写真はありません。上のフォームから最初の1枚を登録してみましょう！")
    else:
        st.caption("💡 新しい写真から順番に並んでいます。画像下のリンクをクリックするとGoogle Drive上で原寸大の確認が可能です。")
        
        cols = st.columns(3)
        for idx, img in enumerate(images):
            col_idx = idx % 3
            with cols[col_idx]:
                with st.container(border=True):
                    st.markdown(f"**{img.get('name')}**")
                    
                    c_time = img.get('createdTime', '')
                    if c_time:
                        try:
                            dt = datetime.datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                            # JSTに変換して表示（+9時間）
                            dt_jst = dt + datetime.timedelta(hours=9)
                            st.caption(f"📅 {dt_jst.strftime('%Y/%m/%d %H:%M')}")
                        except:
                            st.caption(f"📅 {c_time[:10]}")
                    
                    thumb = img.get('thumbnailLink')
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    else:
                        st.caption("（プレビュー不可）")
                        
                    st.markdown(f"[🔗 原寸大で確認・ダウンロード]({img.get('webViewLink')})")