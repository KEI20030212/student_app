# utils/pdf_generator.py

import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

def generate_payslip_pdf(data, month_str):
    """
    合算された1人分の給与データを受け取り、明細書PDFを作成する。
    data の構造例:
    {
        "講師名": "山田太郎", "単価_11": 1500, "単価_12": 1800, "単価_13": 2000,
        "単価_交_田端": 500, "単価_交_東十条": 800, "役職手当": 10000, "交通費合計": 1300,
        "田端": {"11": 4, "12": 2, "13": 0, "days": 1},
        "東十条": {"11": 0, "12": 3, "13": 1, "days": 1}
    }
    """
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # --- 1. タイトルと宛名 ---
    c.setFont('HeiseiKakuGo-W5', 20)
    c.drawCentredString(297, 750, f"{month_str}分 給与明細書")
    
    c.setFont('HeiseiKakuGo-W5', 14)
    c.drawString(50, 680, f"{data['講師名']} 様")
    c.line(50, 675, 250, 675)
    
    # -----------------------------------------------------
    # 🌟 給与の計算（PDF内でも計算して検証）
    # -----------------------------------------------------
    p11 = data["単価_11"]; p12 = data["単価_12"]; p13 = data["単価_13"]
    t_data = data["田端"]; h_data = data["東十条"]
    
    # コマの合計
    total_11 = t_data["11"] + h_data["11"]
    total_12 = t_data["12"] + h_data["12"]
    total_13 = t_data["13"] + h_data["13"]
    
    # 授業給の計算
    salary_11 = total_11 * p11
    salary_12 = total_12 * p12
    salary_13 = total_13 * p13
    total_class_salary = salary_11 + salary_12 + salary_13
    
    # 最終支給額
    final_salary = total_class_salary + data["交通費合計"] + data["役職手当"]

    # --- 2. 最終支給額 ---
    c.setFont('HeiseiKakuGo-W5', 16)
    c.rect(50, 620, 200, 30)
    c.drawString(60, 630, "総支給額")
    c.drawRightString(240, 630, f"{final_salary:,} 円")

    # --- 3. 授業コマ数の内訳（校舎別） ---
    y_pos = 580
    c.setFont('HeiseiKakuGo-W5', 14)
    c.drawString(50, y_pos, "■ 授業コマ数 内訳")
    y_pos -= 20
    
    c.setFont('HeiseiKakuGo-W5', 12)
    
    # 【田端新町校】
    if t_data["11"] > 0 or t_data["12"] > 0 or t_data["13"] > 0:
        c.drawString(70, y_pos, f"【田端新町校】  1:1（{t_data['11']}コマ）  /  1:2（{t_data['12']}コマ）  /  1:3（{t_data['13']}コマ）")
        y_pos -= 20
        
    # 【東十条駅前校】
    if h_data["11"] > 0 or h_data["12"] > 0 or h_data["13"] > 0:
        c.drawString(70, y_pos, f"【東十条駅前校】1:1（{h_data['11']}コマ）  /  1:2（{h_data['12']}コマ）  /  1:3（{h_data['13']}コマ）")
        y_pos -= 20

    y_pos -= 10
    
    # --- 4. 支給額の詳細 ---
    c.setFont('HeiseiKakuGo-W5', 14)
    c.drawString(50, y_pos, "■ 支給額 詳細")
    y_pos -= 20
    
    c.setFont('HeiseiKakuGo-W5', 12)
    step = 25
    
    # 項目を描画するヘルパー関数
    def draw_row(label, detail, amount):
        nonlocal y_pos
        c.drawString(70, y_pos, label)
        c.drawString(200, y_pos, detail)
        c.drawRightString(450, y_pos, f"{amount:,} 円")
        c.setDash(1, 2)
        c.line(70, y_pos - 5, 450, y_pos - 5)
        c.setDash()
        y_pos -= step

    # 授業給
    if total_11 > 0: draw_row("授業給 (1:1)", f"{p11:,} 円 × {total_11} コマ", salary_11)
    if total_12 > 0: draw_row("授業給 (1:2)", f"{p12:,} 円 × {total_12} コマ", salary_12)
    if total_13 > 0: draw_row("授業給 (1:3)", f"{p13:,} 円 × {total_13} コマ", salary_13)
    
    # 交通費
    if t_data["days"] > 0 or h_data["days"] > 0:
        t_str = f"田端 {t_data['days']}日" if t_data['days'] > 0 else ""
        h_str = f"東十条 {h_data['days']}日" if h_data['days'] > 0 else ""
        join_str = " / " if t_str and h_str else ""
        draw_row("交通費", f"出勤日数： {t_str}{join_str}{h_str}", data["交通費合計"])

    # 役職手当
    if data["役職手当"] > 0:
        draw_row("役職手当", "当月分", data["役職手当"])

    # フッター
    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawRightString(500, 50, "※本明細に関するお問い合わせは塾長まで")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_invoice_pdf(data_dict, month_str):
    """請求書PDF作成関数（変更なし）"""
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont('HeiseiKakuGo-W5', 22)
    c.drawCentredString(297, 750, f"{month_str}分 授業料請求書")

    c.setFont('HeiseiKakuGo-W5', 16)
    c.drawString(50, 680, f"{data_dict['👤 生徒名']} 様")
    c.line(50, 675, 250, 675)

    c.setFont('HeiseiKakuGo-W5', 18)
    c.drawString(300, 650, f"合計請求金額： {data_dict['💴 今月の請求額 (円)']:,} 円")

    c.setFont('HeiseiKakuGo-W5', 12)
    y_pos = 580
    items = [
        ("基本コース", data_dict['📚 契約コース']),
        ("実際の受講数", f"{data_dict['📝 実際の受講数']} 回"),
        ("追加コマ数", f"{data_dict['➕ 追加コマ']} 回"),
        ("特別割引（無料コマ）", f"- {data_dict.get('🉐 割引コマ', 0)} 回")
    ]

    for label, value in items:
        c.drawString(80, y_pos, label)
        c.drawRightString(450, y_pos, value)
        c.setDash(1, 2)
        c.line(80, y_pos - 5, 450, y_pos - 5)
        c.setDash()
        y_pos -= 40

    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawString(50, 150, "【お振込先】")
    c.drawString(50, 135, "〇〇銀行 〇〇支店 普通 1234567")
    c.drawString(50, 120, "口座名義：〇〇塾 代表 〇〇〇〇")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()