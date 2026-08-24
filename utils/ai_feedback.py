import google.generativeai as genai
import streamlit as st
import json

def generate_ai_feedback(student_name, subject, homework_status, concentration, report_text):
    """
    授業ログからAIフィードバック(Y列)とスコア(Z列)を自動生成する関数
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return "B", f"APIキー設定エラー: {str(e)}"

    ai_model_name = st.secrets.get("GEMINI_MODEL_NAME", "gemini-3.6-flash")
    model = genai.GenerativeModel(ai_model_name)
    
    prompt = f"""
    あなたは学習塾のプロの教室長です。
    以下の講師が書いた授業報告書（ログ）を読み、講師に対する「フィードバックコメント」と、「報告書の品質スコア（S, A, B, C）」を作成してください。

    【今回の授業情報】
    ・生徒名: {student_name}
    ・科目: {subject}
    ・宿題の実施状況: {homework_status}
    ・授業中の様子（集中力など）: {concentration}
    ・講師が書いた報告コメント: {report_text}

    【評価基準（スコア）】
    S: 生徒の具体的なつまずきや、それに対する具体的な指導内容、次回の改善策が明確に書かれている。素晴らしいレポート。
    A: 指導内容は書かれているが、さらに具体的な声かけや生徒の反応があるとより良くなる。
    B: 事実の羅列（「〇〇をやりました」）のみで、講師の考察や具体的な指導内容が薄い。
    C: 文字数が極端に少ない、または内容が不十分。ネガティブな事実のみで改善の対策がない。

    【フィードバックのトーン＆マナー】
    ・講師のモチベーションが上がるよう、まずは「お疲れ様です！」「〇〇の記載、素晴らしいですね！」とポジティブに褒めてください。
    ・その上で、スコアに応じて「次回はこうするともっと良くなりますよ」という具体的なアドバイスを1〜2文で添えてください。
    ・文字数は150〜200文字程度に収めてください。

    【出力形式】
    以下のJSON形式でのみ出力してください。挨拶や他のテキストは絶対に含めないでください。
    {{
        "score": "A",
        "comment": "お疲れ様です！本日の指導ありがとうございます..."
    }}
    """
    
    try:
        # AIに考えてもらう
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # 🌟 改善：AIが余計な文字をつけてきても、データ部分だけを抜き取る処理
        clean_text = response_text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        try:
            # データをシステムで使える形に変換
            result = json.loads(clean_text)
            return str(result.get("score", "B")), str(result.get("comment", response_text))
            
        except json.JSONDecodeError:
            # 🌟 失敗した場合、AIが何を喋ったのかをそのままスプレッドシートに書き込む（原因特定用）
            return "B", f"【AI回答の形式エラー】{response_text}"
            
    except Exception as e:
        # 🌟 APIの通信そのものに失敗した場合、本当のエラー理由を書き込む
        error_msg = str(e)
        if "403" in error_msg or "API_KEY_INVALID" in error_msg:
            return "B", "APIキーが間違っているか、有効になっていません。(認証エラー)"
        else:
            return "B", f"API通信エラー: {error_msg}"