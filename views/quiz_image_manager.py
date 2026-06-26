import streamlit as st
import pandas as pd
import datetime
import time
import io
from PIL import Image

from utils.g_sheets import get_student_master
# 🌟 変更点: delete_file_from_drive を新しくインポートに追加！
from utils.g_drive import upload_image_to_drive, list_student_images, delete_file_from_drive
from utils.api_guard import robust_api_call

def cached_get_student_master():
    df = robust_api_call(get_student_master, fallback_value=pd.DataFrame())
    return df.copy() if not df.empty else df

# 🌟 新設：画像リスト取得をキャッシュ化してファイルアップローダーの通信を絶対に邪魔させない！
@st.cache_data(ttl=60, show_spinner=False)
def cached_list_student_images(student_id, student_name):
    return robust_api_call(list_student_images, student_id, student_name, fallback_value=[])

def process_image_quality(file_bytes):
    """文字が読める画質をキープしたまま、サイズを適正化して超軽量化する関数"""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 🌟 自動リサイズ（長辺を最大1600ピクセルに制限）
        max_size = 1600
        width, height = img.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        out_buf = io.BytesIO()
        img.save(out_buf, format="JPEG", quality=90, subsampling=0)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        return file_bytes, None

def render_quiz_image_manager_page():
    st.header("📸 小テスト・画像管理")
    st.write("生徒の小テストの答案やノートの写真を、Google Driveへ高画質で保存・確認できます✨")

    df_students_raw = cached_get_student_master()
    df_students = df_students_raw.copy()
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

    st.info("💡 **アップロードのコツ:** スマホ標準のカメラアプリでピントを合わせて綺麗に撮影し、以下の枠からアップロードしてください。複数枚まとめて選択できます！")

    uploaded_files = st.file_uploader(
        "📂 写真ファイルを選択してください (複数選択可・JPG / PNG)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True, 
        key=f"files_{student_id}"
    )

    if uploaded_files:
        st.success(f"📸 {len(uploaded_files)} 枚の画像が選択されています。")
        
        with st.container(border=True):
            st.markdown("**🏷️ 保存するファイルの設定（選択した全画像に適用されます）**")
            c_meta1, c_meta2 = st.columns(2)
            subj = c_meta1.selectbox("教科", ["英語", "数学", "国語", "理科", "社会", "その他"], key=f"meta_sub_{student_id}")
            title_suffix = c_meta2.text_input("補足名 (任意)", placeholder="単元名やテスト名（例: 二次関数）", key=f"meta_title_{student_id}")
            
            if st.button("🚀 この設定でGoogle Driveへ一括保存する", type="primary", use_container_width=True):
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                success_count = 0
                now_date = datetime.date.today().strftime("%Y%m%d")
                suffix_str = f"_{title_suffix}" if title_suffix.strip() else ""
                
                for i, u_file in enumerate(uploaded_files):
                    status_text.text(f"⚡ 画像を軽量化して送信中... ({i+1}/{len(uploaded_files)}枚目)")
                    
                    file_bytes = u_file.getvalue()
                    
                    file_bytes, new_mime = process_image_quality(file_bytes)
                    mime_type = new_mime if new_mime else u_file.type
                    
                    seq_str = f"_{i+1}" if len(uploaded_files) > 1 else ""
                    file_name = f"{now_date}_{subj}{suffix_str}{seq_str}.jpg"

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
                        success_count += 1
                    else:
                        st.error(f"❌ 【{file_name}】の保存に失敗しました: {result}")
                        
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                status_text.empty()
                if success_count > 0:
                    st.success(f"✅ {success_count} 枚の画像をサクサク保存完了しました！")
                    st.cache_data.clear() # 🌟 追加：新しく保存されたので画像キャッシュを強制クリア！
                    time.sleep(1.5)
                    st.rerun()

    # ==========================================
    # 🖼️ 過去の答案ギャラリー表示セクション
    # ==========================================
    st.divider()
    st.subheader("🖼️ 過去の画像ギャラリー")
    
    # 🌟 変更：毎回生通信する古い関数から、高速なキャッシュ版関数に変更
    images = cached_list_student_images(student_id, student_name)

    if not images:
        st.info("まだこの生徒のフォルダに写真はありません。")
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
                            dt_jst = dt + datetime.timedelta(hours=9)
                            Garner = dt_jst.strftime('%Y/%m/%d %H:%M')
                            st.caption(f"📅 {Garner}")
                        except:
                            st.caption(f"📅 {c_time[:10]}")
                    
                    thumb = img.get('thumbnailLink')
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    else:
                        st.caption("（プレビュー不可）")
                        
                    st.markdown(f"[🔗 原寸大で確認・ダウンロード]({img.get('webViewLink')})")
                    
                    # ==========================================
                    # 🗑️ 誤操作防止付き画像削除エリア
                    # ==========================================
                    with st.popover("🗑️ この画像を削除", use_container_width=True):
                        st.warning("⚠️ 本当に削除しますか？\nGoogle Driveから完全に消去され、元に戻せなくなります。")
                        
                        if st.button("🔴 完全に削除する", key=f"del_{img.get('id')}", use_container_width=True):
                            with st.spinner("Driveから削除中..."):
                                success = robust_api_call(
                                    delete_file_from_drive, 
                                    file_id=img.get('id'), 
                                    fallback_value=False
                                )
                                if success:
                                    st.success("削除しました！")
                                    st.cache_data.clear() # 🌟 追加：削除が成功したので画像キャッシュを強制クリア！
                                    time.sleep(1)
                                    st.rerun() 
                                else:
                                    st.error("通信エラーにより削除できませんでした。")