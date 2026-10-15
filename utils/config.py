# utils/config.py

"""
システム全体で利用する定数・設定・IDを管理するファイルです。
ここに集約することで、校舎が増えたりシートが変わった際のメンテナンスが一箇所で済みます。
"""

# ==========================================
# 📊 振替申請用
# ==========================================
# メインのシステム管理用スプレッドシート（元々 g_sheets.py にあったものなどを想定）
# SPREADSHEET_ID = "ここにメインのシートIDがあれば記述"

# 🏫 校舎ごとの振替・欠席連絡用スプレッドシートID
TRANSFER_SHEET_IDS = {
    "田端新町校": "1j93KTSKjywAQoslEPt-osRMzOMSiheb8GrT77gLgPko",
    "東十条駅前校": "1lY7t4gmeFClaWuVOC1DUb-18d3rK81OU5P_F5DabJeQ"
}

# ==========================================
# 📊 学習時間ダッシュボード用
# ==========================================

# ① 画像を生成するためのGAS (Google Apps Script) のURL
SELF_STUDY_GAS_URLS = {
    "田端新町校": {
        "小学生": "https://script.google.com/macros/s/AKfycbxmaI040Qm0iDYykcP14JWw-eID_jeh_2oauTpW6ysYtYkdamtgn4uMLDYts72AQ71s/exec",
        "中学生": "https://script.google.com/macros/s/AKfycbyFMRO5HJXNH7rh8TELMU5DXta_1qINJ41AexRe5KX0kOMDu-kXMG5ZJxNkiYgHSmQn7w/exec",
        "高校生": "https://script.google.com/macros/s/AKfycbxEXhITzJWJrW7P_LdI1tEzFFm8p3YwoEUQ5u_-ZGmQj_GzV3dCbRJRk4a8v2SeEBgz/exec"
    },
    "東十条駅前校": {
        "小学生": "https://script.google.com/macros/s/AKfycbzzCAbe8J24XICaGNR57qD9ui_yO7Dc2D-SrZxTxRiVU77YMM0xvGC7eO0wpHxhC5IF/exec",
        "中学生": "https://script.google.com/macros/s/AKfycbybDCaLgbVei66H7XdQgCaALoA0s1k-4lLuuIaESdRN5AYAwoROTLnJCU4bbp-wBhvf/exec",
        "高校生": "https://script.google.com/macros/s/AKfycbz-_v6lPKqWQUpzMiZ8ExrwY722jmAbfI2Xmf2J6Lz0Z2S6HPx50KIoZMAth7lk8DEVKA/exec"
    }
}

# ② セル(C1, D1)に直接年月を書き込むためのスプレッドシートID
SELF_STUDY_SHEET_IDS = {
    "田端新町校": {
        "小学生": "1V4ID3wirXoTM3M-rdZeYhfu0wrVE19wu3AZOod2XVJ0",
        "中学生": "1Tbbz7SO0-chcOlUwsDjTVhAYQ9zXNhopfwSPFpByD9A",
        "高校生": "1nnFJo8k81VBuz232gAZYVnSX47YgLuaU8Mqt1hzuS_M"
    },
    "東十条駅前校": {
        "小学生": "1n0NvREF5Sf8WHMVOXXHCfm6EhsYDtcDd0qB4dXMR4c8",
        "中学生": "1okTYoVDhBfZzjcq5bVBeMxqc-7Ocv1Woz4JISDI3vGQ",
        "高校生": "12fWkakGZPt8it_OxZNmddDOimzM0CTmCrD2GS5mIX2U"
    }
}

# 認証用シークレットキー
SELF_STUDY_SECRET_KEY = "juku-graph-2026"

# ==========================================
# 📂 Google Drive 連携用設定
# ==========================================

# 🌟 大元フォルダ（生徒のフォルダや書庫が作られる親フォルダ）のID
GDRIVE_MAIN_FOLDER_ID = "1PptAgfwzUT-wR5bPyYHaCO_olsEzi8FS"

# 🌟 答案画像や書庫ファイルのアップロード・削除処理を担当する GAS (Google Apps Script) のウェブアプリURL
GDRIVE_GAS_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw5HuhPiaY8TwX190H5ya9uLDOsHqiT706n51vHDjHFCmd_sTQQb0654q2QyBavOTGqyA/exec"