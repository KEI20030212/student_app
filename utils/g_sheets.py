import streamlit as st
from datetime import datetime, timedelta, timezone
import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import math
import time
import streamlit.components.v1 as components
import base64
import altair as alt # 座標グラフを描くための魔法の絵の具

def get_jst_now():
    """現在時刻を日本時間(JST)で取得する"""
    jst = datetime.timezone(datetime.timedelta(hours=9), 'JST')
    
    # 🌟 ポイント： datetime.datetime.now(...) と2回重ねる！
    return datetime.datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
# --------------------------------------------------
# ⚙️ 設定（デザインとファイル連携）
# --------------------------------------------------
SPREADSHEET_ID = '1fEyisztEGteS22kF1lUlsXiwjmMh1cR7MiXU6aDiZEA'
@st.cache_resource
def get_gc_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    secret_dict = json.loads(st.secrets["gcp_service_account_json"])
    credentials = Credentials.from_service_account_info(secret_dict, scopes=scopes)
    return gspread.authorize(credentials)

#改良版コード
#汎用
@st.cache_data(ttl=600) # 10分間キャッシュ
def get_all_logs():
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("授業ログ統合")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def get_student_logs(student_name):
    df = get_all_logs()
    if df.empty:
        return df
    # 特定の生徒名でフィルタリング
    student_df = df[df["名前"] == student_name]
    return student_df

def ensure_global_sheets(sh):
    titles = [ws.title for ws in sh.worksheets()]
    if "設定_掲示板" not in titles:
        ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
        ws.update_cell(1, 1, "ここに先生たちへの連絡事項を入力してください。")
    if "成績_定期テスト" not in titles:
        ws = sh.add_worksheet(title="成績_定期テスト", rows="1000", cols="15")
        ws.append_row(['日時', '生徒名', 'テスト種別', '英語', '数学', '国語', '理科', '社会', '総合', '偏差値', '保体', '技術', '家庭', '音楽', '9科総合'])
    if "設定_小テスト一覧" not in titles:
        ws = sh.add_worksheet(title="設定_小テスト一覧", rows="100", cols="2")
        ws.append_row(['テスト名', 'スプレッドシートID'])
    if "設定_生徒情報" not in titles:
        ws = sh.add_worksheet(title="設定_生徒情報", rows="100", cols="7")
        ws.append_row(['生徒名', '学年', '学校名', '志望校・目的', '受講科目', '能力', 'やる気'])

def _raw_get_student_master():
    """
    【裏方専用】Googleスプレッドシートから直接データを取得する（生通信）
    ※この関数は外から直接呼ばない
    """
    import pandas as pd
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_生徒情報")
    return pd.DataFrame(ws.get_all_records(numericise_ignore=["all"]))

@st.cache_data(ttl=600)
def get_student_master():
    """
    【全画面からの窓口】
    ここで robust_api_call を使って安全に通信し、成功した結果だけを10分間キャッシュする最強の盾！
    """
    from utils.api_guard import robust_api_call
    import pandas as pd
    
    # 生通信関数を robust_api_call で守りながら実行
    return robust_api_call(_raw_get_student_master, fallback_value=pd.DataFrame())

@st.cache_data(ttl=60)
def get_student_info(student_name):#「特定の生徒1人だけの詳細情報」が欲しいときに使う
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_生徒情報")
    records = ws.get_all_records()
    for r in records:
        if r.get('生徒名') == str(student_name):
            return r
    return {}

#home.py
@st.cache_data(ttl=120)
def load_board_message():
    """掲示板のメッセージを取得する"""
    gc = get_gc_client()
    for attempt in range(3):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            
            # 💡 改善ポイント：元の「except:」だと全てのエラーを飲み込んでしまうので、
            # 「シートが見つからないエラー」の時だけ新しくシートを作るように限定しました！
            try:
                ws = sh.worksheet("設定_掲示板")
            except gspread.exceptions.WorksheetNotFound: 
                ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
                ws.update_cell(1, 1, "メッセージ")
                ws.update_cell(2, 1, "本日の連絡事項はありません。")
            
            val = ws.cell(2, 1).value
            return val if val else "本日の連絡事項はありません。"
            
        except gspread.exceptions.APIError:
            # Googleが悲鳴を上げたら（APIエラー）
            if attempt < 2:
                time.sleep(2) # 2秒深呼吸してやり直し
            else:
                # 3回やってもダメだった場合は、システム全体が止まらないように仮の文字を返す
                return "⚠️ 現在システムが混み合っています。数分待ってから画面を更新（リロード）してください。"

def save_board_message(message):
    """掲示板のメッセージを保存する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_掲示板")
    except:
        ws = sh.add_worksheet(title="設定_掲示板", rows="10", cols="2")
        ws.update_cell(1, 1, "メッセージ")
    ws.update_cell(2, 1, message)
    st.cache_data.clear()

@st.cache_data(ttl=60)
def get_my_messages(receiver_id):
    """自分（receiver_id）宛てのメッセージを取得する"""
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("連絡_メッセージ")
        all_vals = ws.get_all_values()
        
        my_msgs = []
        target_id = str(receiver_id).strip().lower()
        
        for row in all_vals[1:]: # ヘッダーを飛ばす
            if len(row) >= 3 and str(row[2]).strip().lower() == target_id:
                my_msgs.append({
                    "送信日時": row[0],
                    "送信者ID": row[1],
                    "受信者ID": row[2],
                    "メッセージ内容": row[3],
                    "状態": row[4] if len(row) >= 5 else "未読" # 🌟 5列目を取得！
                })
        # 新しい順に並び替え
        return sorted(my_msgs, key=lambda x: x['送信日時'], reverse=True)
    except Exception as e:
        return []

def get_all_accounts(force_refresh=False):
    """設定_アカウントシートからIDとパスワードのリストを取得"""
    import streamlit as st
    
    # ① 強制リフレッシュの指示が出た時、またはまだ記憶がない時だけ読みに行く
    if force_refresh or 'all_accounts' not in st.session_state:
        gc = get_gc_client() 
        sh = gc.open_by_key(SPREADSHEET_ID) 
        
        try:
            ws = sh.worksheet("設定_アカウント")
            records = ws.get_all_records(numericise_ignore=["all"])
            
            # IDをキーにした辞書に変換します
            accounts = {}
            for row in records:
                if row.get('ID'):
                    accounts[str(row['ID'])] = row
                    
            # ② 【重要】ここで、取得したデータをStreamlitの脳内に保存する！
            st.session_state['all_accounts'] = accounts
            
        except Exception as e:
            st.error("アカウントシートの読み込みに失敗しました。")
            return {}

    # ③ もし記憶があればそれをそのまま返すし、新しく取得した場合もそれを返す
    return st.session_state['all_accounts']

def mark_messages_as_read(receiver_id):
    """自分が受信者のメッセージを「既読」に書き換える関数"""
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("連絡_メッセージ")
        
        # シートの全データを一括で取得（高速化のため）
        all_values = ws.get_all_values()
        target_receiver = str(receiver_id).strip().lower()
        
        # 2行目から順番にチェック（1行目はヘッダーなので飛ばす）
        for i, row in enumerate(all_values):
            if i == 0:
                continue
            
            # 列の数が足りない場合（空行など）のエラーを防止
            if len(row) < 3:
                continue
                
            # C列(インデックス2)が受信者ID、E列(インデックス4)が状態
            sheet_receiver = str(row[2]).strip().lower()
            status = str(row[4]).strip() if len(row) >= 5 else ""
            
            # 「自分宛て」かつ「既読以外（未読やFalseなど）」の場合
            if sheet_receiver == target_receiver and status != "既読":
                # i は0始まり、スプレッドシートの行は1始まりなので「i + 1」
                # E列は5番目の列なので「5」を指定して「既読」に上書き
                ws.update_cell(i + 1, 5, "既読")
                
    except Exception as e:
        print(f"既読処理に失敗しました: {e}")

#attendance_seat.py
@st.cache_data(ttl=60)
def load_seating_data():
    """スプレッドシートから最新の座席情報を取得する"""
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("設定_座席表")
    except:
        ws = sh.add_worksheet(title="設定_座席表", rows="20", cols="5")
        ws.append_row(["ブース", "生徒名", "状態"])
        for i in range(1, 7):
            ws.append_row([f"ブース{i}", "-- 空席 --", "出席"])
            
    records = ws.get_all_records()
    seating = {}
    for r in records:
        seating[str(r.get("ブース", ""))] = {
            "生徒名": str(r.get("生徒名", "-- 空席 --")),
            "状態": str(r.get("状態", "出席"))
        }
    
    if not seating:
        return {f"ブース{i}": {"生徒名": "-- 空席 --", "状態": "出席"} for i in range(1, 7)}
        
    return seating

def save_seating_data(seating_dict):
    """座席情報をスプレッドシートに上書き保存する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet("設定_座席表")
    except:
        ws = sh.add_worksheet(title="設定_座席表", rows="20", cols="5")
        
    ws.clear() 
    
    data_to_append = [["ブース", "生徒名", "状態"]]
    for booth, info in seating_dict.items():
        data_to_append.append([booth, info["生徒名"], info["状態"]])
        
    for row in data_to_append:
        ws.append_row(row)

#student_portal.pyで使用
# 🌟 変更：引数の最後に contract_course="" を追加
def update_student_info(student_id, name, grade, school, target, subjects, ability, motivation, naishin, dev_score, hw_rate, exam_status="未設定", school_type="未設定", contract_course=""):
    import gspread # もし上でimportされていなければ必要です
    gc = get_gc_client() 
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_生徒情報")
    
    all_data = ws.get_all_values()
    header = all_data[0]
    
    # 🌟 変更：契約コースの列がなければ自動で作るように追加
    required_cols = ['内申点', '最新偏差値', '宿題履行率', '受験区分', '学校区分', '契約コース']
    for col in required_cols:
        if col not in header:
            ws.update_cell(1, len(header) + 1, col)
            header.append(col)

    row_index = -1
    for i, row in enumerate(all_data):
        if row[0] == str(student_id): 
            row_index = i + 1 
            break

    # 🌟 改善ポイント1: 既存のデータを取得しておく（他の列が消えるのを防ぐため）
    existing_row = all_data[row_index - 1] if row_index != -1 else [""] * len(header)

    row_dict = {
        '生徒ID': str(student_id),
        '生徒名': name,
        '学年': grade,
        '学校名': school,
        '志望校・目的': target,
        '受講科目': subjects,
        '能力': ability,
        'やる気': motivation,
        '内申点': naishin,
        '最新偏差値': dev_score,
        '宿題履行率': hw_rate,
        '受験区分': exam_status,
        '学校区分': school_type,
        '契約コース': contract_course # 🌟 追加：ここで受け取った契約コースをセット
    }

    # 🌟 改善ポイント2: 辞書にない列（保護者の電話番号など）は既存データをそのまま残す
    row_to_save = []
    for i, col in enumerate(header):
        if col in row_dict:
            row_to_save.append(row_dict[col])
        else:
            # 既存のデータがあればそれを、なければ空白を入れる
            val = existing_row[i] if i < len(existing_row) else ""
            row_to_save.append(val)

    if row_index != -1:
        range_label = f"A{row_index}:{gspread.utils.rowcol_to_a1(row_index, len(header))}"
        ws.update(range_name=range_label, values=[row_to_save])
        print(f"ID:{student_id} のデータを更新しました。")
    else:
        ws.append_row(row_to_save)
        print(f"ID:{student_id} を新規登録しました。")
        
    import streamlit as st
    st.cache_data.clear()

def get_student_quiz_records(student_name):
    """
    スプレッドシートの「小テスト記録」シートから、指定した生徒の記録を取得する
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("小テスト記録") 
        
        all_records = worksheet.get_all_values()
        quiz_records = []
        
        # 列の構成 (Pythonは0から数えます)
        # 0:日時, 1:名前, 2:テキスト, 3:単元, 4:点数, 5:ミス問題番号, 6:実施形態
        
        # 1行目（ヘッダー）を飛ばして2行目からループ
        for row in all_records[1:]:
            # データが5列以上あり、かつ「名前(row[1])」が選択した生徒と一致するかチェック
            if len(row) >= 5 and row[1] == student_name:
                
                # 「テキスト」と「単元」を組み合わせてテスト名にする（例: "英単語ターゲット_Unit1"）
                quiz_name = f"{row[2]}_{row[3]}" 
                score = row[4]
                
                quiz_records.append({"quiz_name": quiz_name, "score": score})
                
        return quiz_records
        
    except Exception as e:
        print(f"小テスト記録の読み込みエラー: {e}")
        return [] # エラー時は空のリストを返す

def save_test_score(date, name, test_type, eng, math_score, jpn, sci, soc, 
                    dev_eng=None, dev_math=None, dev_jpn=None, dev_sci=None, dev_soc=None, 
                    dev_3=None, dev_5=None, 
                    pe=None, tech=None, home=None, mus=None, art=None, is_naishin=False,
                    att_eng=None, att_math=None, att_jpn=None, att_sci=None, att_soc=None, # 🌟 態度を追加
                    att_pe=None, att_gika=None, att_art=None, att_mus=None):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("成績_定期テスト")
    
    header = ws.row_values(1)
    
    # 🌟 「態度」用のカラムを required_cols に追加
    required_cols = [
        '偏差値_英語', '偏差値_数学', '偏差値_国語', '偏差値_理科', '偏差値_社会', 
        '英語 偏差値', '数学 偏差値', '国語 偏差値', '理科 偏差値', '社会 偏差値', 
        '偏差値_3科', '偏差値_5科', '保体', '技術', '家庭', '美術', '音楽', '9科総合', 
        '英語 内申', '数学 内申', '国語 内申', '理科 内申', '社会 内申',
        '保体 内申', '技家 内申', '美術 内申', '音楽 内申',
        '英語 態度', '数学 態度', '国語 態度', '理科 態度', '社会 態度', # 🌟 追加
        '保体 態度', '技家 態度', '美術 態度', '音楽 態度' # 🌟 追加
    ]
    missing_cols = [col for col in required_cols if col not in header]
    
    if missing_cols:
        if len(header) + len(missing_cols) > ws.col_count:
            ws.add_cols(len(missing_cols) + 5)
        for col_name in missing_cols:
            ws.update_cell(1, len(header) + 1, col_name)
            header.append(col_name)

    row_dict = {
        '日時': date.strftime("%Y/%m/%d"), '生徒名': name, 'テスト種別': test_type,
    }

    if is_naishin:
        # 🌟 UIのセレクトボックスの未選択 ("") を考慮し、値がなければ "-" を入れる
        row_dict.update({
            '英語 内申': eng if eng is not None else "-",
            '数学 内申': math_score if math_score is not None else "-",
            '国語 内申': jpn if jpn is not None else "-",
            '理科 内申': sci if sci is not None else "-",
            '社会 内申': soc if soc is not None else "-",
            '保体 内申': pe if pe is not None else "-",
            '技家 内申': tech if tech is not None else "-", 
            '美術 内申': art if art is not None else "-",  
            '音楽 内申': mus if mus is not None else "-",
            '英語 態度': att_eng if att_eng else "-",   # 🌟 追加
            '数学 態度': att_math if att_math else "-", # 🌟 追加
            '国語 態度': att_jpn if att_jpn else "-",   # 🌟 追加
            '理科 態度': att_sci if att_sci else "-",   # 🌟 追加
            '社会 態度': att_soc if att_soc else "-",   # 🌟 追加
            '保体 態度': att_pe if att_pe else "-",     # 🌟 追加
            '技家 態度': att_gika if att_gika else "-", # 🌟 追加
            '美術 態度': att_art if att_art else "-",   # 🌟 追加
            '音楽 態度': att_mus if att_mus else "-"    # 🌟 追加
        })
    else:
        total_5 = sum([x for x in [eng, math_score, jpn, sci, soc] if x is not None])
        total_9 = total_5 + sum([x for x in [pe, tech, home, mus, art] if x is not None]) if test_type == "期末テスト" else "-"

        row_dict.update({
            '英語': eng if eng is not None else "-", '数学': math_score if math_score is not None else "-",
            '国語': jpn if jpn is not None else "-", '理科': sci if sci is not None else "-",
            '社会': soc if soc is not None else "-", '総合': total_5, 
            
            '偏差値_英語': dev_eng if dev_eng is not None else "-",
            '偏差値_数学': dev_math if dev_math is not None else "-",
            '偏差値_国語': dev_jpn if dev_jpn is not None else "-",
            '偏差値_理科': dev_sci if dev_sci is not None else "-",
            '偏差値_社会': dev_soc if dev_soc is not None else "-",
            
            '英語 偏差値': dev_eng if dev_eng is not None else "-",
            '数学 偏差値': dev_math if dev_math is not None else "-",
            '国語 偏差値': dev_jpn if dev_jpn is not None else "-",
            '理科 偏差値': dev_sci if dev_sci is not None else "-",
            '社会 偏差値': dev_soc if dev_soc is not None else "-",
            
            '偏差値_3科': dev_3 if dev_3 is not None else "-",
            '偏差値_5科': dev_5 if dev_5 is not None else "-",
            '保体': pe if pe is not None else "-", '技術': tech if tech is not None else "-",
            '家庭': home if home is not None else "-", '音楽': mus if mus is not None else "-",
            '美術': art if art is not None else "-", 
            '9科総合': total_9
        })
    
    row_to_append = [row_dict.get(col, "-") for col in header]
    ws.append_row(row_to_append)
    st.cache_data.clear()

#conference_report.py
def load_quiz_data_from_dedicated_sheet(student_name):
    """
    小テスト専用シートから特定の生徒のデータだけを読み込む
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("小テスト記録")
        
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return pd.DataFrame()
            
        # その生徒のデータだけに絞り込む
        return df[df['名前'] == student_name]
    except Exception as e:
        return pd.DataFrame()

#multi_input.pyで使用
def get_all_teacher_names():
    """講師マスタから講師名のリストを取得して五十音順にする"""
    gc = get_gc_client() # 👈 先生の環境に合わせた接続！
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)

        sheet = sh.worksheet("講師マスタ")
        
        names = sheet.col_values(1)[1:] # 1行目の見出しを飛ばしてA列を取得
        names = sorted([name.strip() for name in names if name.strip()])
        return names
        
    except Exception as e:
        import streamlit as st
        st.error(f"🚨 講師マスタの取得に失敗しました！原因: {e}")
        return []

def save_to_spreadsheet(student_id, name, subject, text_name, advanced_p, quiz_records, date, teacher_name="未入力", class_type="1:1", attendance="出席（通常）", class_slot="-", advice="-", parent_msg="-", next_handover="-", assigned_p=0, completed_p=0, motivation_rank=0, next_hw_text="-", next_hw_pages=0, late_time="-", concentration="-", reaction="-"):
    # 🌟 生徒IDも表示するようにプリント文をパワーアップ！
    print(f"🌟🌟🌟 保存処理スタート！ ID:{student_id} 生徒名:{name} 🌟🌟🌟") 
    
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 🌟 革命ポイント！「授業ログ統合」シートだけを狙い撃ち！
        # （生徒ごとのシートを探したり作ったりする処理は全カットで超高速化）
        worksheet = sh.worksheet("授業ログ統合")
        
        date_str = date.strftime("%Y/%m/%d") if hasattr(date, 'strftime') else str(date)
        
        # 🚨 超重要ポイント！
        # リストの2番目に「student_id」を追加しました！
        if not quiz_records:
            worksheet.append_row([date_str, student_id, name, subject, text_name, advanced_p, "-", "-", "-", teacher_name, class_type, attendance, class_slot, advice, parent_msg, next_handover, assigned_p, completed_p, motivation_rank, next_hw_text, next_hw_pages, late_time, concentration, reaction])
        else:
            for q in quiz_records:
                worksheet.append_row([date_str, student_id, name, subject, text_name, advanced_p, f"第{q['unit']}章", q['score'], "-", teacher_name, class_type, attendance, class_slot, advice, parent_msg, next_handover, assigned_p, completed_p, motivation_rank, next_hw_text, next_hw_pages, late_time, concentration, reaction])
        return True
    except Exception as e:
        import streamlit as st
        st.error(f"🚨 スプレッドシートの書き込みでエラーが発生しました: {e}")
        return False

def get_last_handover(name, subject):
    """
    「授業ログ統合」シートから、特定の科目の「最新の引継ぎ事項」を抜き出す関数
    """
    try:
        df = get_all_logs() # 🌟 キャッシュされた統合データを爆速で読み込み！
        
        if df.empty or '名前' not in df.columns or '科目' not in df.columns or '次回への引継ぎ' not in df.columns:
            return "（シートの項目が正しく設定されていません）"
            
        # 名前と科目でフィルタリング（絞り込み）
        student_df = df[(df['名前'] == name) & (df['科目'] == subject)]
        
        if student_df.empty:
            return f"（{subject} の過去の記録は見つかりませんでした）"
            
        # 一番下の行（最新）を取得
        last_note = student_df['次回への引継ぎ'].iloc[-1]
        
        # 空欄やハイフン、NaN（無効な値）などをチェック
        if pd.notna(last_note) and str(last_note).strip() not in ["", "-", "nan"]:
            return str(last_note)
        else:
            return "（前回の引継ぎ事項は空欄でした）"
            
    except Exception as e:
        return f"（データ取得エラー: {e}）"

def get_last_homework_info(name, subject):
    """
    「授業ログ統合」シートから、前回の『次回の宿題テキスト』と『ページ数（範囲）』を探し出す関数
    """
    try:
        df = get_all_logs()
        if df.empty or '名前' not in df.columns or '科目' not in df.columns:
            return "なし", "-"
            
        if '次回の宿題テキスト' not in df.columns or '次回の宿題ページ数' not in df.columns:
            return "なし", "-"

        # 名前と科目でフィルタリング
        student_df = df[(df['名前'] == name) & (df['科目'] == subject)]
        
        if student_df.empty:
            return "なし", "-"
            
        text_name = student_df['次回の宿題テキスト'].iloc[-1]
        pages = student_df['次回の宿題ページ数'].iloc[-1]
        
        # NaN対策と文字化
        text_name_str = str(text_name).strip() if pd.notna(text_name) else ""
        pages_str = str(pages).strip() if pd.notna(pages) else ""

        final_text = text_name_str if text_name_str and text_name_str not in ["-", "nan"] else "なし"
        final_pages = pages_str if pages_str and pages_str != "nan" else "-"
        
        return final_text, final_pages
        
    except Exception as e:
        return "なし", "-"

def get_last_page_from_sheet(name, subject): # 🌟 引数に subject を追加！
    """
    「授業ログ統合」シートから、特定の科目の前回の終了ページ（進捗）を探し出す関数
    """
    try:
        df = get_all_logs()
        if df.empty or '名前' not in df.columns or '科目' not in df.columns:
            return 0
            
        # 🌟 名前と科目でフィルタリング（絞り込み）
        student_df = df[(df['名前'] == name) & (df['科目'] == subject)]
        
        if student_df.empty:
            return 0
            
        # 統合シートの列名「終了ページ」または旧「ページ数」を探す
        col_name = '終了ページ' if '終了ページ' in df.columns else 'ページ数' if 'ページ数' in df.columns else None
        
        if not col_name:
            return 0
            
        last_page = student_df[col_name].iloc[-1]
        
        # 空っぽの場合は 0 を返す
        if pd.isna(last_page) or str(last_page).strip() in ["", "-", "nan"]:
            return 0
            
        try:
            # 昔のデータ（純粋な数字）なら、今まで通り整数にする
            return int(float(last_page))
        except ValueError:
            # 新しいデータ（「P.10〜20」など）や複数行の文字なら、そのまま文字として返す
            return str(last_page)
            
    except Exception as e:
        return 0

def save_self_study_record(date, name, start_time, end_time, break_time, actual_minutes, content, points):
    """自習の記録を「自習記録」シートに保存する（APIエラー対策版）"""
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            gc = get_gc_client()
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.worksheet("自習記録")
            
            row_data = [
                str(date),
                name,
                str(start_time),
                str(end_time),
                break_time,
                actual_minutes,
                content,
                points
            ]
            
            worksheet.append_row(row_data)
            return True, "成功"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2) # 失敗したら2秒待って再試行
                continue
            return False, str(e)

def add_new_textbook(new_name):
    """
    アプリから新規テキストを登録し、自動で五十音順（A列基準）に全列を並べ替える魔法！
    """
    import streamlit as st
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("テキスト情報一覧")
        
        # 🌟 5列構成（テキスト, 章, 単元名, 開始ページ, 終了ページ）に合わせて追加
        worksheet.append_row([new_name, "-", "-", "-", "-"])
        
        # 🌟 ここが自動並べ替えの魔法！
        # 1行目（ヘッダー）は残したまま、A列〜E列（5列目）までを1列目（テキスト名）の昇順でまとめてソートします
        worksheet.sort((1, 'asc'), range='A2:E1000')
        return True
    except Exception as e:
        st.error(f"🚨 新規テキストの裏側でエラー発生: {e}")
        return False

def get_textbook_master():
    """テキストと章、および単元名を取得する"""
    import streamlit as st
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("テキスト情報一覧") 
        
        # 🌟 ゼロ落ち（01 が 1 になるバグ）を防ぐため numericise_ignore を追加
        records = worksheet.get_all_records(numericise_ignore=["all"])
        
        master_dict = {}
        for row in records:
            text_name = str(row.get("テキスト", "")).strip()
            chap = str(row.get("章", "")).strip()
            # 🌟 新しく追加した「単元名」列（または章名）を読み取る
            chap_name = str(row.get("単元名", row.get("章名", ""))).strip()
            
            if text_name and chap:
                if text_name not in master_dict:
                    # リストではなく、章番号をキーにした辞書にする
                    master_dict[text_name] = {}
                master_dict[text_name][chap] = chap_name
                
        return master_dict
        
    except Exception as e:
        import pandas as pd
        print(f"マスタ取得の裏側でエラー発生: {e}")
        return {}

def update_student_homework_rate(student_name, *args):
    """
    統合ログから今月の宿題・小テストデータを集計し、
    生徒マスターの「宿題履行率」と「やる気ランク」を自動更新する関数
    """
    from utils.calc_logic import calculate_quiz_points, calculate_motivation_rank
    import datetime
    import pandas as pd
    
    # 🌟 1. 統合シートから全授業ログを一括取得（キャッシュ経由で爆速）
    df_all = get_all_logs()
    if df_all.empty or "APIエラー発生" in df_all.columns: 
        return
        
    name_col = '名前' if '名前' in df_all.columns else '生徒名'
    df_student = df_all[df_all[name_col] == student_name].copy()
    
    if df_student.empty:
        return

    # 🌟 2. 「今月」のデータに絞り込み
    df_student['日時'] = pd.to_datetime(df_student['日時'], format='mixed', errors='coerce')
    today = datetime.date.today()
    df_this_month = df_student[
        (df_student['日時'].dt.month == today.month) & 
        (df_student['日時'].dt.year == today.year)
    ]

    if df_this_month.empty:
        return

    # 🌟 3. 今月の「宿題ページ数」の合計を出す
    total_assigned = 0
    total_completed = 0

    # 列名の揺れ吸収（統合シートの設定に合わせる）
    assigned_col = '出した宿題P' if '出した宿題P' in df_this_month.columns else '指示ページ数'
    completed_col = 'やった宿題P' if 'やった宿題P' in df_this_month.columns else '実施ページ数'

    if assigned_col in df_this_month.columns and completed_col in df_this_month.columns:
        total_assigned = pd.to_numeric(df_this_month[assigned_col], errors='coerce').fillna(0).sum()
        total_completed = pd.to_numeric(df_this_month[completed_col], errors='coerce').fillna(0).sum()

    # 宿題履行率の計算
    if total_assigned > 0:
        hw_rate = min(100.0, (total_completed / total_assigned) * 100)
    else:
        hw_rate = 0.0
    hw_rate = round(hw_rate, 1)

    # 🌟 4. 今月の小テストのポイントを計算（小テスト統合シートから取得！）
    df_quiz = load_quiz_records()
    total_points = 0
    if not df_quiz.empty and "APIエラー発生" not in df_quiz.columns:
        q_name_col = '名前' if '名前' in df_quiz.columns else '生徒名'
        df_q_student = df_quiz[df_quiz[q_name_col] == student_name].copy()
        
        if not df_q_student.empty:
            df_q_student['日時'] = pd.to_datetime(df_q_student['日時'], format='mixed', errors='coerce')
            df_q_month = df_q_student[
                (df_q_student['日時'].dt.month == today.month) & 
                (df_q_student['日時'].dt.year == today.year)
            ]
            if '点数' in df_q_month.columns:
                scores = pd.to_numeric(df_q_month['点数'], errors='coerce').dropna()
                for s in scores:
                    total_points += calculate_quiz_points(s)
            
    # 🌟 5. 新しいやる気ランクを算出
    new_motivation = calculate_motivation_rank(hw_rate, total_points, 0)
    
    # 🌟 6. 生徒マスター（設定_生徒情報）を直接更新する裏方処理へ渡す
    _update_student_master_row(student_name, hw_rate, new_motivation)

def _update_student_master_row(student_name, hw_rate, motivation_rank):
    """設定_生徒情報シートの該当生徒の行だけをピンポイントで更新する裏方関数"""
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("設定_生徒情報")
        all_data = ws.get_all_values()
        
        if len(all_data) <= 1: return
        header = all_data[0]
        
        try:
            name_idx = header.index("生徒名")
            hw_idx = header.index("宿題履行率")
            mot_idx = header.index("やる気ランク")
        except ValueError:
            return # 列が見つからない場合は処理しない
        
        # 生徒を探して該当するマスだけを直接上書き
        for i in range(1, len(all_data)):
            if all_data[i][name_idx] == student_name:
                ws.update_cell(i + 1, hw_idx + 1, f"{hw_rate}%")
                ws.update_cell(i + 1, mot_idx + 1, motivation_rank)
                # キャッシュもクリアして次の画面表示を最新に保つ
                if hasattr(get_student_master, "clear"):
                    get_student_master.clear()
                break
    except Exception as e:
        print(f"生徒マスター更新エラー: {e}")

#dashboard.py
def load_quiz_records():
    """
    全員共通の「小テスト記録」シートから全データを読み込む
    """
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        # 固定で「小テスト記録」という名前のシートを開く
        return pd.DataFrame(sh.worksheet("小テスト記録").get_all_records())
    except Exception as e:
        print(f"Error loading quiz records: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_quiz_maker_sheets():
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    
    # get_all_records() は1行目を見出し(キー)として取得してくれます
    records = ws.get_all_records()

    quiz_data = {}
    for row in records:
        name = str(row.get('テスト名', ''))
        if name:
            # 💡 空文字や文字列対策：確実に「数値」に変換する！
            raw_marks = row.get('満点', 100)
            try:
                # 文字列の "20" などもここで数値(float)になる
                full_marks = float(raw_marks)
            except ValueError:
                # 空文字 "" などで変換に失敗した場合は100点とする
                full_marks = 100.0 
                
            # 🌟 【ここを追加！】スプレッドシートから「用紙サイズ」を取得する
            # ※「用紙サイズ」という列がない、または空欄の場合は "A4" にします
            raw_size = str(row.get('用紙サイズ', 'A4')).strip()
            paper_size = raw_size if raw_size else "A4"
                
            quiz_data[name] = {
                "id": str(row.get('スプレッドシートID', '')),
                "full_marks": full_marks, # 数値化したものをセット
                "サイズ": paper_size      # 🌟 ここで取得したサイズも一緒に保存！
            }
    return quiz_data

def get_student_self_study_points(student_name):
    """「自習記録」シートから、指定した生徒の累計獲得ポイントを取得する"""
    try:
        gc = get_gc_client() 
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("自習記録")
        
        all_records = worksheet.get_all_values()
        total_points = 0
        
        for row in all_records[1:]:
            if len(row) >= 8 and row[1] == student_name:
                try:
                    total_points += int(row[7])
                except ValueError:
                    continue
                    
        return total_points
        
    except Exception as e:
        print(f"自習ポイントの読み込みエラー: {e}")
        return 0

@st.cache_data(ttl=60)
def load_test_scores():
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("成績_定期テスト")
    return pd.DataFrame(ws.get_all_records())

#self_study_dashboard.py
def load_self_study_data():
    """自習記録シートから全データを取得してシステム用の表（データフレーム）にして返す"""
    try:
        # 👇👇 🚨 ここにも鍵を取り付けました！！ 🚨 👇👇
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        worksheet = sh.worksheet("自習記録")
        # 1行目が見出し（日付、生徒名…）になっている前提で全データを取得
        data = worksheet.get_all_records()
        import pandas as pd
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        print(f"自習記録の読み込みエラー: {e}")
        import pandas as pd
        return pd.DataFrame()

#quiz_dashboard.py
def get_quiz_master_dict():
    """
    「設定_小テスト一覧」シートから、テスト名と満点・用紙サイズの対応表を取得する
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("設定_小テスト一覧")
        
        # get_all_values() はデータをリストの形で取得します
        all_records = worksheet.get_all_values()
        master_dict = {}
        
        # 1行目（ヘッダー）を飛ばしてループ
        # A列:テキスト名(row[0]), B列:単元名(row[1]), C列:満点(row[2]), D列:用紙サイズ(row[3]) と仮定
        for row in all_records[1:]:
            if len(row) >= 3:
                # 記録シート側の quiz_name と合わせるため「テキスト_単元」をキーにする
                quiz_key = f"{row[0]}_{row[1]}"
                
                # C列（満点）の取得
                try:
                    full_marks = float(row[2])
                except ValueError:
                    full_marks = 100 # 数字でない場合はデフォルト100点
                    
                # 🌟 【ここを追加！】D列（用紙サイズ）の取得
                # 行のデータが4つ以上ある ＆ 空欄じゃない場合はそのサイズを使い、それ以外は「A4」にする安全策
                if len(row) >= 4 and row[3].strip() != "":
                    paper_size = row[3].strip()
                else:
                    paper_size = "A4"
                
                # 🌟 【ここを変更！】辞書の中に "サイズ" も一緒に保存する
                master_dict[quiz_key] = {
                    "full_marks": full_marks,
                    "サイズ": paper_size
                }
                
        return master_dict
    except Exception as e:
        print(f"小テスト設定の読み込みエラー: {e}")
        return {}

def save_quiz_to_dedicated_sheet(date_str, student_name, text_name, chapter, score, w_nums, mode):
    """
    小テスト専用シートに記録を保存する
    mode: "授業内" または "自習"
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("小テスト記録")
        
        row_data = [
            date_str,      # 日時
            student_name,  # 名前
            text_name,     # テキスト
            chapter,       # 単元
            score,         # 点数
            w_nums,        # ミス問題番号
            mode           # 実施形態（授業内/自習）
        ]
        
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"小テスト保存エラー: {e}")
        return False

#quiz_maker.py
def add_quiz_maker_sheet(test_name, sheet_id, full_marks, paper_size="A4"): # 🌟 ここに full_marks を追加！
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    ws.append_row([test_name, sheet_id, full_marks, paper_size])
    st.cache_data.clear()

def delete_quiz_maker_sheet(test_name):
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("設定_小テスト一覧")
    cell = ws.find(test_name, in_column=1)
    if cell: ws.delete_rows(cell.row)
    st.cache_data.clear()

#school_homework.py
@st.cache_data(ttl=60) # 短めのキャッシュでリアルタイム性を確保
def load_school_homework_data():
    """学校の課題データを全件取得（APIエラー対策版）"""

    gc = get_gc_client()
    max_retries = 5
    for attempt in range(max_retries):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("学校課題管理")
            data = ws.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                st.error(f"データ取得に失敗しました: {e}")
                return pd.DataFrame()

def update_homework_status(row_index, new_status):
    """課題のステータスを更新（row_indexはDataFrameのインデックス+2）"""

    gc = get_gc_client()
    for attempt in range(3):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("学校課題管理")
            # ステータス列（F列 = 6番目）を更新
            ws.update_cell(row_index, 6, new_status)
            return True
        except Exception:
            time.sleep(2)
    return False

def add_school_homework_multi(student_list, subject, task_list, deadline, memo):
    """
    複数人の生徒に対し、複数の課題を一括で登録する
    task_list: ['課題1', '課題2', ...] というリスト形式
    """
    if not student_list or not task_list:
        return False, "生徒または課題が空です。"

    gc = get_gc_client()
    max_retries = 3
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    deadline_str = deadline.strftime("%Y-%m-%d")
    
    # 全生徒 × 全課題 の行データを作成
    rows_to_add = []
    for task in task_list:
        for student in student_list:
            rows_to_add.append([
                now_str,
                student,
                subject,
                task,      # ここがループで回ってきた各課題
                deadline_str,
                "未着手",
                memo
            ])

    last_error = ""
    for attempt in range(max_retries):
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet("学校課題管理")
            ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
            return True, "成功"
        except Exception as e:
            last_error = str(e)
            time.sleep(2)
            
    return False, last_error

#search_page.py
def delete_specific_log(student_id, student_name, date_str, period):
    """
    「授業ログ統合」シートから、指定した生徒・日付・授業コマの記録を探して削除する関数
    """
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("授業ログ統合")
        
        all_data = ws.get_all_values()
        if len(all_data) <= 1:
            return False
            
        header = all_data[0]
        
        # 各列のインデックスを取得
        try:
            id_idx = header.index("生徒ID") if "生徒ID" in header else -1
            name_idx = header.index("名前") if "名前" in header else header.index("生徒名")
            date_idx = header.index("日時")
            period_idx = header.index("授業コマ") # 🌟 「科目」ではなく「授業コマ」を探す
        except ValueError:
            return False

        # 下の行（最新）から順番に探す
        for i in range(len(all_data) - 1, 0, -1):
            row = all_data[i]
            
            row_date = str(row[date_idx]).replace("-", "/")
            target_date = date_str.replace("-", "/")
            
            # 日付と授業コマが一致するかチェック！
            if target_date in row_date and row[period_idx] == period:
                if id_idx != -1 and str(row[id_idx]) == str(student_id):
                    ws.delete_rows(i + 1)
                    return True
                elif row[name_idx] == student_name:
                    ws.delete_rows(i + 1)
                    return True
                    
        return False
    except Exception as e:
        print(f"削除エラー: {e}")
        return False

#message_sender.py
def save_message(sender_id, receiver_id, message):
    """メッセージを「連絡_メッセージ」シートに保存する関数"""
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID) # ※SPREADSHEET_KEYの部分は、先生の環境に合わせてください
        ws = sh.worksheet("連絡_メッセージ")
        
        now = get_jst_now()
        
        # スプレッドシートの A列〜E列 に合わせて保存
        # E列の「既読」は、送った瞬間は未読なので "False" にしておきます
        ws.append_row([now, sender_id, receiver_id, message, "未読"])
        return True
        
    except Exception as e:
        import streamlit as st
        st.error(f"メッセージの保存に失敗しました: {e}")
        return False

def get_sent_messages(sender_id):
    """自分（sender_id）が送信したメッセージ履歴を取得する"""
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("連絡_メッセージ")
        all_vals = ws.get_all_values()
        
        sent_msgs = []
        target_id = str(sender_id).strip().lower()
        
        for row in all_vals[1:]: # ヘッダーを飛ばす
            if len(row) >= 2 and str(row[1]).strip().lower() == target_id:
                sent_msgs.append({
                    "送信日時": row[0],
                    "送信者ID": row[1],
                    "受信者ID": row[2],
                    "メッセージ内容": row[3],
                    "状態": row[4] if len(row) >= 5 else "未読" # 🌟 5列目を取得！
                })
        # 新しい順に並び替え
        return sorted(sent_msgs, key=lambda x: x['送信日時'], reverse=True)
    except Exception as e:
        return []

#my_salary.py
@st.cache_data(ttl=600)
def load_published_salary():
    """先生用のページで公開済みの給与データを読み込む"""
    try:
        gc = get_gc_client()
        # 👇 読み込み処理をすべて try の中に入れるのが最大のポイント！
        sh = gc.open_by_key(SPREADSHEET_ID) 
        ws = sh.worksheet("給与公開用データ")
        return pd.DataFrame(ws.get_all_records())
        
    except Exception as e:
        # 🌟 もしシートが無い、APIエラーが起きたなどの場合はすべてここで受け止める
        st.error("⚠️ 給与データの読み込みに失敗しました。スプレッドシートのIDや共有設定を確認してください。")
        return pd.DataFrame() # 空のデータを返して連鎖エラーを防ぐ

#account_manager.py
def add_new_account(user_id, password, teacher_name, role):
    """新しいアカウントをスプレッドシートに追加する"""
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("設定_アカウント") # 👈 実際のアカウント管理シート名に合わせてください
        ws.append_row([user_id, password, teacher_name, role])
        return True
    except Exception as e:
        import streamlit as st
        st.error(f"🚨 アカウントの保存に失敗しました: {e}")
        return False

def delete_account(user_id):
    """
    指定されたユーザーIDのスプレッドシート行を削除する。
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        ws = sh.worksheet("設定_アカウント") 
        
        try:
            # 1列目（A列）からユーザーIDを検索
            cell = ws.find(user_id, in_column=1)
            # 見つかったらその行をごっそり削除
            ws.delete_rows(cell.row)
            return True
        except gspread.exceptions.CellNotFound:
            # 万が一IDが見つからなかった場合
            print(f"ユーザーID '{user_id}' が見つかりませんでした。")
            return False
            
    except Exception as e:
        print(f"アカウント削除エラー: {e}")
        return False

def update_account_role(user_id, new_role):
    """
    指定したユーザーIDの権限（role）を更新する裏方関数
    """
    gc = get_gc_client()
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("設定_アカウント")  
        all_values = ws.get_all_values()
        
        if len(all_values) <= 1:
            return False
            
        header = all_values[0]
        
        try:
            # 🌟 ここを "ユーザーID" から "ID" に修正しました！
            id_idx = header.index("ID") 
            role_idx = header.index("権限")
        except ValueError:
            print("列名が見つかりません。「ID」または「権限」の列が存在するか確認してください。")
            return False
        
        # 該当するユーザーIDを探して、権限のマスだけを上書き
        for i in range(1, len(all_values)):
            if str(all_values[i][id_idx]) == str(user_id):
                ws.update_cell(i + 1, role_idx + 1, new_role)
                return True
                
        return False # 見つからなかった場合
    except Exception as e:
        print(f"アカウント権限更新エラー: {e}")
        return False

#tuition_dashboard.py
@st.cache_data(ttl=3600)
def load_billing_data(year_month):
    """指定した年月の請求データを取得する"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    
    try:
        worksheet = sh.worksheet("請求管理")
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame()
        
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    
    if not df.empty and '年月' in df.columns:
        ym_no_zero = year_month.replace("年0", "年") 
        filtered_df = df[(df['年月'] == year_month) | (df['年月'] == ym_no_zero)]
        return filtered_df
        
    return pd.DataFrame()

def save_billing_data(year_month, edited_df):
    """請求データを保存（上書き）する"""
    import pandas as pd
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("請求管理")
    
    all_data = worksheet.get_all_records()
    df_all = pd.DataFrame(all_data)
    
    edited_df = edited_df.copy()
    edited_df.insert(0, '年月', year_month)
    
    if not df_all.empty and '年月' in df_all.columns:
        df_keep = df_all[df_all['年月'] != year_month]
        df_final = pd.concat([df_keep, edited_df], ignore_index=True)
    else:
        df_final = edited_df
        
    df_final = df_final.fillna("")
        
    worksheet.clear()
    worksheet.update([df_final.columns.values.tolist()] + df_final.values.tolist())
    return True

def load_price_master():
    """料金マスタを読み込み、データの型を整えて取得する"""
    df = pd.DataFrame() 
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("料金マスタ")
    
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        if '学年' in df.columns:
            df['学年'] = df['学年'].astype(str).str.strip()
        
        for col in ['コマ数', '料金', '追加単価']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0

    return df

#salary_dashboard.py
def load_instructor_master():
    """
    スプレッドシートの「講師マスタ」シートのデータを読み込む
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        ws = sh.worksheet("講師マスタ")
        records = ws.get_all_records()
        
        return pd.DataFrame(records)
    except Exception as e:
        print(f"講師マスタ読み込みエラー: {e}")
        return pd.DataFrame(columns=["講師名", "1:1単価", "1:2単価", "1:3単価", "交通費", "役職手当"])

def update_instructor_master(df_updated):
    """
    画面上で編集されたデータフレームを「講師マスタ」シートに全体上書き保存する
    """
    try:
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet("講師マスタ")
        
        # 1. 今シートにある古いデータを一旦まっさらにクリアする
        ws.clear()
        
        # 2. DataFrameをスプレッドシートに書き込める形（リストのリスト）に変換する
        # （1行目にヘッダー、2行目以降にデータが入る形になります）
        data_to_write = [df_updated.columns.tolist()] + df_updated.values.tolist()
        
        # 3. A1セルを起点にして、新しいデータを一気にドーンと書き込む
        # ※もしここでエラーが出る場合は、 gspreadのバージョンに合わせて ws.update('A1', data_to_write) に変更してみてください。
        ws.update(data_to_write, 'A1') 
        
        # 4. Streamlitのキャッシュをクリアして、次回から最新状態が読み込まれるようにする
        import streamlit as st
        st.cache_data.clear()
        
    except Exception as e:
        print(f"講師マスタ更新エラー: {e}")

def publish_salary_data(year_month, df_summary):
    """計算済みの給与データを「公開給与」シートに保存（上書き）する"""
    try:
        import pandas as pd
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 🌟 1. シートの存在確認（なければ作成、あれば取得）
        try:
            worksheet = sh.worksheet("公開給与")
        except gspread.exceptions.WorksheetNotFound:
            # シートがない場合は新規作成（1行目にヘッダーを自動で入れる）
            worksheet = sh.add_worksheet(title="公開給与", rows="100", cols="20")
        
        # 🌟 2. 既存の全データを取得
        all_data = worksheet.get_all_records()
        df_all = pd.DataFrame(all_data)
        
        # 🌟 3. 保存するデータに「年月」列を追加
        df_to_save = df_summary.copy()
        # 既存の「年月」列があれば一旦削除して、最新のものを先頭に差し込む
        if '年月' in df_to_save.columns:
            df_to_save = df_to_save.drop(columns=['年月'])
        df_to_save.insert(0, '年月', year_month)
        
        # 🌟 4. 重複上書きロジック
        if not df_all.empty and '年月' in df_all.columns:
            # 今回保存する月「以外」のデータを残す
            df_keep = df_all[df_all['年月'] != year_month]
            # 残した過去データと、今回の新しいデータを合体
            df_final = pd.concat([df_keep, df_to_save], ignore_index=True)
        else:
            df_final = df_to_save
            
        # 🌟 5. 【最重要】NaN（欠損値）を空文字("")に変換
        # これがないと Google Sheets API は高確率でエラーになります
        df_final = df_final.fillna("")
        
        # 全データが空の場合の安全策
        if df_final.empty:
            return False

        # 🌟 6. スプレッドシートへの書き込み
        worksheet.clear()
        # カラム名とデータを合体させて更新
        data_to_upload = [df_final.columns.values.tolist()] + df_final.values.tolist()
        worksheet.update(values=data_to_upload, range_name="A1")
        
        return True
        
    except Exception as e:
        import streamlit as st
        # 詳細なエラー内容をコンソール（またはログ）に出力
        print(f"給与公開エラー詳細: {e}")
        return False

def load_salary_data(month):
    """
    「公開給与」シートから指定された年月の給与データだけを取得する関数
    """
    try:
        import pandas as pd
        import gspread
        gc = get_gc_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # 1. シートの存在確認
        try:
            worksheet = sh.worksheet("公開給与")
        except gspread.exceptions.WorksheetNotFound:
            # まだ一度も給与ダッシュボードで「公開」ボタンが押されていない（シートが無い）場合は空っぽで返す
            return pd.DataFrame()
            
        # 2. データの取得
        all_data = worksheet.get_all_records()
        if not all_data:
            return pd.DataFrame()
            
        df_all = pd.DataFrame(all_data)
        
        # 3. 指定された「年月」のデータだけを絞り込んで返す
        if '年月' in df_all.columns:
            df_filtered = df_all[df_all['年月'] == month].copy()
            return df_filtered
        else:
            return pd.DataFrame()
            
    except Exception as e:
        print(f"給与データ読み込みエラー: {e}")
        import pandas as pd
        return pd.DataFrame()

#profit_loss_dashboard.py
def load_fixed_costs():
    """固定費（家賃など）を読み込む"""
    gc = get_gc_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    
    try:
        worksheet = sh.worksheet("固定費設定")
    except gspread.exceptions.WorksheetNotFound:
        return pd.DataFrame(columns=["項目", "金額"])
        
    return pd.DataFrame(worksheet.get_all_records())

