const chatInput = document.querySelector(".chat-input input");
const chatButton = document.querySelector(".chat-input button");
const chatBox = document.querySelector(".chat-box");
const pushContextButton = document.querySelector(".push-context-btn");

const CHAT_BASE_API = "http://localhost:8000/chat/";
const PUSH_CONTEXT_API = "http://localhost:8000/chat/page-content/";
const SESSION_ID = "chat-x1y2z3";

initChat();

chatButton.addEventListener("click", () => {
  sendChatMessage();
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendChatMessage();
  }
});

pushContextButton.addEventListener("click", () => {
  alert("Pushing web context to RAG chatbot backend");
  pushWebContext();
});

function createChatMessage(message, fromBot = false) {
  var message = message
    .replace(/\n/g, "<br>")
    .replace(/^\s+/gm, "&nbsp;")
    .trim();

  const chatMessage = document.createElement("div");
  chatMessage.classList.add("chat-message");
  if (fromBot) {
    chatMessage.classList.add("chat-message-left");
  } else {
    chatMessage.classList.add("chat-message-right");
  }
  chatMessage.innerHTML = `
        <div class="chat-message-content">
            <p>${message}</p>
        </div>
    `;
  chatBox.appendChild(chatMessage);
}

function createInputMessageTemplate(selection) {
  if (!selection) return;

  var inputMessageTemplate = `Help me understand "${selection}"`;
  chatInput.value = inputMessageTemplate;
  return inputMessageTemplate;
}

async function sendChatMessage() {
  const message = chatInput.value;
  if (message) {
    createChatMessage(message, false);
    chatInput.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    var response = await fetch(CHAT_BASE_API, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: message,
        session_id: SESSION_ID,
      }),
    });
    var data = await response.json();
    createChatMessage(data, true);
    chatBox.scrollTop = chatBox.scrollHeight;

    return data;
  }
  return;
}

async function initChat() {
  var chatPort = chrome.runtime.connect({ name: "chat" });
  await chatPort.onMessage.addListener(function (msg) {
    selection = msg.context;
    createInputMessageTemplate(selection);
  });
}

async function pushWebContext() {
  var pageContext = await fetchPageContent();
  console.log("pageContext", pageContext);
  //   send pageContext to RAG chatbot backend endpoint
  await fetch(PUSH_CONTEXT_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      context: pageContext,
      session_id: SESSION_ID,
    }),
  });
  return chatPort;
}

function fetchPageContent() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs.length === 0) {
        return reject(new Error("No active tab found"));
      }

      // ignore if tab url starts with chrome://
      if (tabs[0].url.startsWith("chrome://")) {
        return reject(new Error("Cannot access chrome:// pages"));
      }

      chrome.tabs.sendMessage(tabs[0].id, { pageContent: true }, (response) => {
        if (chrome.runtime.lastError) {
          return reject(new Error(chrome.runtime.lastError.message));
        }

        if (!response || !response.content) {
          return reject(new Error("No content found in the response"));
        }

        resolve(response.content);
      });
    });
  });
}
