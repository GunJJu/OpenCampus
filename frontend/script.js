// 상수 정의
const API_URL = "http://127.0.0.1:5500/api/chat";
const ERROR_MESSAGES = {
  SERVER: (status) => `서버 오류가 발생했어요. (${status}) 잠시 후 다시 시도해 주세요. 😢`,
  NETWORK: "네트워크 오류가 발생했어요. 😢",
  EMPTY_REPLY: "응답이 비어있어요.",
};

// DOM 요소 참조
const chatBody = document.getElementById("chatBody");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const personaSelect = document.getElementById("personaSelect");
const statusEmoji = document.getElementById("statusEmoji");
const statusText = document.getElementById("statusText");

/**
 * 메시지 버블을 채팅 영역에 추가하는 함수
 * @param {string} text - 메시지 텍스트
 * @param {string} sender - 발신자 ("user" | "bot")
 */
function addMessageBubble(text, sender = "user") {
  const row = document.createElement("div");
  row.classList.add("message-row", sender);

  const bubble = document.createElement("div");
  bubble.classList.add("bubble", sender);
  bubble.textContent = text;

  row.appendChild(bubble);
  chatBody.appendChild(row);
  chatBody.scrollTop = chatBody.scrollHeight;
}

/**
 * 감정 상태 UI 업데이트
 * @param {Object} data - API 응답 데이터
 */
function updateSentimentStatus(data) {
  if (data.sentiment_emoji && data.sentiment_label) {
    statusEmoji.textContent = data.sentiment_emoji;
    statusText.textContent = `현재 감정: ${data.sentiment_label}`;
  }
}

/**
 * 서버에 메시지를 전송하고 응답을 처리하는 함수
 */
async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message) return;

  const persona = personaSelect.value;

  // 사용자 메시지 UI에 추가
  addMessageBubble(message, "user");
  messageInput.value = "";
  messageInput.focus();
  sendBtn.disabled = true;

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, persona }),
    });

    if (!res.ok) {
      await res.json().catch(() => ({}));
      addMessageBubble(ERROR_MESSAGES.SERVER(res.status), "bot");
      return;
    }

    const data = await res.json();
    updateSentimentStatus(data);
    addMessageBubble(data.reply || ERROR_MESSAGES.EMPTY_REPLY, "bot");
  } catch (err) {
    addMessageBubble(ERROR_MESSAGES.NETWORK, "bot");
  } finally {
    sendBtn.disabled = false;
  }
}

// 이벤트 리스너 등록
sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});