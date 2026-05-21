import math
import pandas as pd
import re

# 👇 quiz_name と quiz_master_dict に「=None」をつけて、無くてもOK（オプション）にします！
def calculate_quiz_points(score, quiz_name=None, quiz_master_dict=None):
    try:
        got_score = float(score)
        
        # マスターリストからそのテストの満点を取得（見つからない場合は100点満点とする）
        full_marks = 100
        # 👇 辞書データがちゃんと送られてきた時だけ、辞書から満点をチェックする
        if quiz_master_dict is not None and quiz_name in quiz_master_dict:
            full_marks = quiz_master_dict[quiz_name].get("full_marks", 100)
        
        # 百分率を計算
        percent = (got_score / full_marks) * 100
        
        if percent >= 100: return 20
        elif percent >= 90: return 10
        elif percent >= 80: return 9
        elif percent >= 70: return 8
        elif percent >= 60: return 7
        elif percent >= 50: return 6
        elif percent >= 40: return 5
        elif percent >= 30: return 4
        elif percent >= 20: return 3
        elif percent >= 10: return 2
        else: return 1
    except:
        return 0

# ✨ 新しく追加：宿題履行率を計算する魔法
def calculate_hw_rate(assigned_pages, completed_pages):
    """
    出したページ数とやってきたページ数から履行率(%)を出す。
    1ページも出していない場合は 0% とする。
    """
    try:
        assigned = float(assigned_pages)
        completed = float(completed_pages)
        if assigned <= 0:
            return 0.0
        # 100%を超えることはないので、minで100に抑える
        rate = (completed / assigned) * 100
        return min(100.0, rate)
    except:
        return 0.0

# utils/calc_logic.py にある古い calculate_motivation_rank をこれに差し替え

def calculate_motivation_rank(hw_rate, quiz_pts, self_study_pts=0):
    """宿題履行率(%)と、総合ポイント（小テストpt ＋ 自習pt）からやる気(1〜5)を算出"""
    total_pts = quiz_pts + self_study_pts

    if hw_rate >= 100 and total_pts >= 120: return 5
    elif hw_rate >= 90 and total_pts >= 100: return 4
    elif hw_rate >= 75 and total_pts >= 80: return 3
    elif hw_rate >= 50 and total_pts >= 40: return 2
    else: return 1
def calculate_ability_rank(naishin, dev_score):
    """内申点と偏差値から能力(1〜5)を算出"""
    if naishin >= 5 and dev_score >= 65: return 5
    elif naishin >= 4 and dev_score >= 55: return 4
    elif naishin >= 3 and dev_score >= 45: return 3
    elif naishin >= 2 and dev_score >= 35: return 2
    else: return 1
# 🌟 追加: テキストのページ範囲から進捗ページ数を計算する関数
def calc_pages_from_text(text):
    if pd.isna(text): return 0
    matches = re.findall(r'(\d+)\s*[~〜\-ー]\s*(\d+)', str(text))
    total = 0
    for start_str, end_str in matches:
        total += abs(int(end_str) - int(start_str)) + 1
    return total

def calculate_score_ratio(row, quiz_details):
    """
    小テストの1行データと満点マスタを受け取り、正答率（0.0〜1.0）を計算する魔法
    """
    q_name = str(row.get('テキスト', ''))
    score = pd.to_numeric(row.get('点数', 100), errors='coerce')
    
    if pd.isna(score): 
        return 1.0 # 点数がないエラー行は一旦無視（弱点にしない）
    
    # そのテストの満点を探す
    full_m = 100
    matched_marks = [v["full_marks"] for k, v in quiz_details.items() if k.startswith(f"{q_name}_")]
    if matched_marks:
        full_m = int(pd.Series(matched_marks).mode()[0])
    
    return score / full_m if full_m > 0 else 1.0