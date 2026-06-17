import streamlit as st
import json
import base64
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# 🌟 大元フォルダのID
MAIN_FOLDER_ID = "1PptAgfwzUT-wR5bPyYHaCO_olsEzi8FS" 

# 🌟 GASのウェブアプリURL
GAS_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw5HuhPiaY8TwX190H5ya9uLDOsHqiT706n51vHDjHFCmd_sTQQb0654q2QyBavOTGqyA/exec"

# 🌟 変更点: 削除機能を追加するため、readonlyを外してフルアクセス権限に変更します
SCOPES = ['https://www.googleapis.com/auth/drive'] 

def get_drive_service():
    """Google Drive APIに接続する"""
    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(secret_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

def get_student_folder_id(student_id, student_name):
    """生徒専用のフォルダを探す（作成はせず検索のみ）"""
    service = get_drive_service()
    folder_name = f"{student_id}_{student_name}"
    
    query = f"'{MAIN_FOLDER_ID}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    return None

def get_or_create_student_folder(student_id, student_name):
    """LINE送信用：フォルダIDを取得するラッパー関数"""
    return get_student_folder_id(student_id, student_name)

def upload_image_to_drive(student_id, student_name, file_name, file_bytes, mime_type):
    """GAS（ウェブアプリ）を経由して画像をアップロードする"""
    try:
        b64_data = base64.b64encode(file_bytes).decode('utf-8')
        
        payload = {
            "studentId": student_id,
            "studentName": student_name,
            "fileName": file_name,
            "mimeType": mime_type,
            "fileData": b64_data
        }
        
        response = requests.post(GAS_WEBHOOK_URL, json=payload)
        result = response.json()
        
        if result.get("success"):
            return True, result.get("url")
        else:
            return False, result.get("error")
            
    except Exception as e:
        print(f"Driveアップロードエラー: {e}")
        return False, str(e)

def list_student_images(student_id, student_name):
    """生徒のフォルダ内の画像一覧を取得する"""
    try:
        student_folder_id = get_student_folder_id(student_id, student_name)
        if not student_folder_id:
            return []
            
        service = get_drive_service()
        query = f"'{student_folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink, createdTime, thumbnailLink)',
            orderBy='createdTime desc'
        ).execute()
        
        return results.get('files', [])
    except Exception as e:
        print(f"画像リスト取得エラー: {e}")
        return []

# ==========================================
# 🗑️ 【改善版】画像を「gomi」フォルダへ移動する関数群
# ==========================================

def get_or_create_gomi_folder(service):
    """大元フォルダの中に「gomi」フォルダがあるか探し、なければ作成してIDを返す"""
    query = f"'{MAIN_FOLDER_ID}' in parents and name='gomi' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    
    # 存在しない場合は新規作成
    folder_metadata = {
        'name': 'gomi',
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [MAIN_FOLDER_ID]
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')


def delete_file_from_drive(file_id):
    """指定されたファイルIDの画像を元の生徒フォルダから除外し、「gomi」フォルダへ移動する"""
    try:
        service = get_drive_service()
        
        # 1. 「gomi」フォルダのIDを取得（なければ自動作成）
        gomi_folder_id = get_or_create_gomi_folder(service)
        
        # 2. 現在の画像が入っている親フォルダ（生徒フォルダ）のIDを特定する
        file_info = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file_info.get('parents', []))
        
        if previous_parents:
            # 3. 生徒フォルダから除外（removeParents）し、同時にgomiフォルダへ追加（addParents）
            service.files().update(
                fileId=file_id,
                addParents=gomi_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
        else:
            # 万が一、すでに親フォルダを失っている場合はgomiフォルダに直接紐付ける
            service.files().update(
                fileId=file_id,
                addParents=gomi_folder_id,
                fields='id, parents'
            ).execute()
            
        return True
        
    except Exception as e:
        print(f"Drive画像移動（gomi）エラー: {e}")
        
        # API制限や予期せぬエラー時のセーフティネットとしてゴミ箱移動を試みる
        try:
            service.files().update(fileId=file_id, body={'trashed': True}).execute()
            return True
        except Exception as e2:
            print(f"Drive画像ゴミ箱移動エラー: {e2}")
            return False