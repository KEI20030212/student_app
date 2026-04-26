# utils/pdf_generator.py

import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

def generate_payslip_pdf(data_dict, month_str):
    """
    1人分の給与データを受け取り、PDFファイル（バイナリデータ）を作成して返す関数
    """
    # 日本語フォントの設定（面倒なダウンロード不要の組み込みフォント！）
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    
    # PDFを描き込むための「空の画用紙（メモリ）」を用意
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # --- ここからPDFのデザイン（描画） ---
    
    # 1. タイトル
    c.setFont('HeiseiKakuGo-W5', 20)
    c.drawCentredString(297, 750, f"{month_str}分 給与明細書")
    
    # 2. 宛名
    c.setFont('HeiseiKakuGo-W5', 14)
    c.drawString(50, 680, f"{data_dict['👨‍🏫 担当講師']} 様")
    c.line(50, 675, 250, 675) # 名前の下にアンダーライン
    
    # 3. 明細の内容（項目と金額を並べる）
    c.setFont('HeiseiKakuGo-W5', 12)
    y_pos = 620
    step = 30
    
    # 項目のリスト
    items = [
        ("合計授業コマ数", f"{data_dict['合計コマ数']} コマ"),
        ("授業給", f"{data_dict['授業給 (円)']} 円"),
        ("役職手当", f"{data_dict['役職手当 (円)']} 円"),
        ("出勤日数", f"{data_dict['出勤日数']} 日"),
        ("交通費合計", f"{data_dict['交通費合計 (円)']} 円")
    ]
    
    for label, value in items:
        c.drawString(80, y_pos, label)
        c.drawRightString(400, y_pos, value) # 金額は右揃えで綺麗に！
        c.setDash(1, 2) # 点線にする
        c.line(80, y_pos - 5, 400, y_pos - 5)
        c.setDash() # 実線に戻す
        y_pos -= step
        
    # 4. 最終支給額（四角い枠で囲って目立たせる！）
    c.setFont('HeiseiKakuGo-W5', 16)
    c.rect(70, y_pos - 40, 340, 40) # 枠線
    c.drawString(90, y_pos - 25, "最終支給額（合計）")
    c.drawRightString(390, y_pos - 25, f"{data_dict['💰 最終支給額 (円)']} 円")
    
    # 5. フッター（塾名など）
    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawRightString(500, 50, "※本明細に関するお問い合わせは塾長まで")
    
    # --- 描画終わり ---
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def generate_invoice_pdf(data_dict, month_str):
    """
    1人分の請求データを受け取り、請求書PDF（バイナリ）を作成して返す
    data_dict = {生徒名, 学年, 契約コース, 請求額, 実際の受講数, 追加コマ, 割引コマ}
    """
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # 1. タイトル
    c.setFont('HeiseiKakuGo-W5', 22)
    c.drawCentredString(297, 750, f"{month_str}分 授業料請求書")

    # 2. 宛名と合計金額
    c.setFont('HeiseiKakuGo-W5', 16)
    c.drawString(50, 680, f"{data_dict['👤 生徒名']} 様")
    c.line(50, 675, 250, 675)

    c.setFont('HeiseiKakuGo-W5', 18)
    c.drawString(300, 650, f"合計請求金額： {data_dict['💴 今月の請求額 (円)']:,} 円")

    # 3. 明細
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

    # 4. 振込先案内（例として固定文字）
    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawString(50, 150, "【お振込先】")
    c.drawString(50, 135, "〇〇銀行 〇〇支店 普通 1234567")
    c.drawString(50, 120, "口座名義：〇〇塾 代表 〇〇〇〇")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()