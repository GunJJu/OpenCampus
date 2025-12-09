from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

# Flask 앱 초기화
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Google Gemini API 클라이언트 초기화
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else genai.Client()

# -----------------------------
# 1. 헬퍼 함수: API 응답에서 텍스트 추출
# -----------------------------
def extract_text_from_response(response):
    """Gemini API 응답에서 텍스트를 추출하는 헬퍼 함수"""
    if not response.candidates or len(response.candidates) == 0:
        return None
    
    candidate = response.candidates[0]
    
    # finish_message에서 추출 시도 (MAX_TOKENS일 때)
    if hasattr(candidate, 'finish_message') and candidate.finish_message:
        if (hasattr(candidate.finish_message, 'content') and 
            candidate.finish_message.content and
            hasattr(candidate.finish_message.content, 'parts') and
            candidate.finish_message.content.parts and
            len(candidate.finish_message.content.parts) > 0):
            part = candidate.finish_message.content.parts[0]
            if hasattr(part, 'text') and part.text:
                return part.text.strip()
    
    # 일반적인 경우: candidate.content.parts에서 추출
    if (hasattr(candidate, 'content') and candidate.content and
        hasattr(candidate.content, 'parts') and candidate.content.parts and
        len(candidate.content.parts) > 0):
        part = candidate.content.parts[0]
        if hasattr(part, 'text') and part.text:
            return part.text.strip()
    
    # response.text 직접 사용 시도
    if hasattr(response, 'text') and response.text:
        return str(response.text).strip()
    
    return None


# -----------------------------
# 2. 감정 분석 함수 (Google Gemini API 사용)
# -----------------------------
def analyze_sentiment(text: str):
    """Google Gemini API를 사용하여 감정을 분석하는 함수. 실패 시 None 반환"""
    try:
        sentiment_prompt = (
            f"다음 텍스트의 감정을 분석해주세요: \"{text}\"\n\n"
            "다음 형식으로 JSON만 응답해주세요:\n"
            "{\n"
            '  "sentiment": "happy" | "sad" | "angry" | "surprised" | "neutral",\n'
            '  "label_ko": "행복" | "슬픔" | "화남" | "놀람" | "중립",\n'
            '  "emoji": "😊" | "😢" | "😡" | "😲" | "😐",\n'
            '  "score": -3 ~ 3 사이의 정수 (행복=3, 슬픔=-2, 화남=-3, 놀람=1, 중립=0)\n'
            "}\n\n"
            "텍스트의 맥락과 톤을 고려하여 정확하게 분석해주세요."
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=sentiment_prompt,
            config={
                "temperature": 0.3,
                "max_output_tokens": 2000,
            }
        )
        
        result_text = extract_text_from_response(response)
        
        if result_text:
            import json
            import re
            
            # JSON 추출: 중괄호로 감싸진 JSON 찾기
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_match = re.search(json_pattern, result_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                # 마크다운 코드 블록 제거
                clean_json = re.sub(r'```json\s*', '', json_str)
                clean_json = re.sub(r'```\s*', '', clean_json)
                clean_json = clean_json.strip()
                
                try:
                    result_json = json.loads(clean_json)
                    
                    # 기본값 설정 및 유효성 검사
                    sentiment = result_json.get("sentiment", "neutral")
                    valid_sentiments = ["happy", "sad", "angry", "surprised", "neutral"]
                    if sentiment not in valid_sentiments:
                        sentiment = "neutral"
                    
                    return {
                        "sentiment": sentiment,
                        "label_ko": result_json.get("label_ko", "중립"),
                        "emoji": result_json.get("emoji", "😐"),
                        "score": result_json.get("score", 0),
                    }
                except json.JSONDecodeError:
                    pass
            
            # 전체 텍스트 직접 파싱 시도
            try:
                clean_text = re.sub(r'```json\s*', '', result_text)
                clean_text = re.sub(r'```\s*', '', clean_text)
                clean_text = clean_text.strip()
                result_json = json.loads(clean_text)
                
                sentiment = result_json.get("sentiment", "neutral")
                valid_sentiments = ["happy", "sad", "angry", "surprised", "neutral"]
                if sentiment not in valid_sentiments:
                    sentiment = "neutral"
                
                return {
                    "sentiment": sentiment,
                    "label_ko": result_json.get("label_ko", "중립"),
                    "emoji": result_json.get("emoji", "😐"),
                    "score": result_json.get("score", 0),
                }
            except json.JSONDecodeError:
                pass
        
        return None
        
    except Exception:
        # AI 분석 실패 시 None 반환
        return None


# -----------------------------
# 3. 말투 / 성격 프리셋
# -----------------------------
PERSONAS = {
    "kind_ta": {
        "name": "친절한 조교",
        "prefix": "친절한 조교 톤으로 대답: ",
        "style": "항상 존댓말을 쓰고, 부드럽고 친절하게 설명하며 학생을 응원하는 말투로 대답한다.",
    },
    "cold_engineer": {
        "name": "무뚝뚝한 공대생",
        "prefix": "공대생처럼 짧고 무뚝뚝하게 대답: ",
        "style": "말이 길지 않고 핵심만 콬 집어 말하며, 다소 무뚝뚝하지만 불친절하지는 않은 말투로 대답한다. 츤데레스타일",
    },
    "excited_friend": {
        "name": "과몰입 친구",
        "prefix": "친한 친구처럼 과몰입해서 대답: ",
        "style": "김탄사와, 이모티콘을 적절히 섞어 사용하고, 공감과 리액션이 풍부한 친한 친구 말투로 대답한다.",
    },
}


# -----------------------------
# 4. 답변 생성 함수 (Google Gemini API 사용)
# -----------------------------
def generate_reply(user_message: str, persona_key: str, sentiment_info: dict) -> str:
    """Google Gemini API를 사용하여 페르소나와 감정을 반영한 AI 답변을 생성하는 함수"""
    
    persona = PERSONAS.get(persona_key, PERSONAS["kind_ta"])
    sentiment_label = sentiment_info["label_ko"]
    emoji = sentiment_info["emoji"]

    system_content = (
        "당신은 사용자의 말을 듣고 공감하며 짧게 대답하는 한국어 챗봇입니다. "
        "대답은 최대 3문장 이내로 하고, 말투는 자연스러운 구어체를 사용하세요. "
        "너무 긴 설명보다는 핵심 위주의 대답을 해 주세요."
    )

    user_content = (
        f"당신의 캐릭터(말투): {persona['name']}.\n"
        f"캐릭터 설명: {persona.get('style', '')}\n\n"
        f"사용자의 현재 감정: {sentiment_label} {emoji}\n"
        f"이 감정을 적절히 공감하고 반영해서 대답해 주세요.\n\n"
        f"사용자의 발화: \"{user_message}\"\n\n"
        "규칙:\n"
        "- 반드시 한국어로 대답합니다.\n"
        "- 1~3문장 이내로 짧게 대답합니다.\n"
        "- 필요하다면 이모지는 1~2개 정도만 사용합니다.\n"
    )

    try:
        prompt = f"{system_content}\n\n{user_content}"
        
        # 모델명을 여러 형식으로 시도
        model_names = [
            
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-pro-latest"
        ]
        
        response = None
        last_error = None
        
        for model_name in model_names:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "temperature": 0.7,
                        "max_output_tokens": 2000,
                    }
                )
                break
            except Exception as e:
                last_error = e
                continue
        
        if response is None:
            raise last_error if last_error else Exception("모든 모델 시도 실패")
        
        # 헬퍼 함수로 텍스트 추출
        reply_text = extract_text_from_response(response)
        
        if reply_text:
            return reply_text
        
        raise ValueError("응답에서 텍스트를 추출할 수 없습니다")
        
    except Exception:
        # API 오류 시 연결 실패 메시지 반환
        return "죄송해요 ㅜ AI와 연결이 실패했어요"


# -----------------------------
# 5. API 엔드포인트
# -----------------------------
@app.route("/")
def serve_index():
    """기본 페이지로 static/index.html 제공"""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    """채팅 메시지를 받아 감정 분석 및 답변을 생성하는 API"""
    # OPTIONS 요청 처리 (CORS preflight)
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Invalid request body"}), 400
            
        user_message = data.get("message", "").strip()
        persona = data.get("persona", "kind_ta")

        if not user_message:
            return jsonify({"error": "message is required"}), 400

        # 감정 분석
        sentiment_info = analyze_sentiment(user_message)
        
        # 감정 분석 실패 시
        if sentiment_info is None:
            return jsonify({
                "reply": "죄송해요 ㅜ AI와 연결이 실패했어요",
                "sentiment": "failed",
                "sentiment_label": "AI 연결 실패",
                "sentiment_emoji": "❌",
                "persona": persona,
            })
        
        # 답변 생성
        reply_text = generate_reply(user_message, persona, sentiment_info)

        return jsonify({
            "reply": reply_text,
            "sentiment": sentiment_info["sentiment"],
            "sentiment_label": sentiment_info["label_ko"],
            "sentiment_emoji": sentiment_info["emoji"],
            "persona": persona,
        })
    except Exception as e:
        return jsonify({"error": "서버 오류가 발생했습니다.", "details": str(e)}), 500


if __name__ == "__main__":
    # 개발 환경용
    app.run(host="0.0.0.0", port=5500, debug=True)