import {userId, initData, backButton} from "../common/telegram.js";
import {initBottomNav} from "../common/i18n.js";
import {logEvent} from "../common/api.js";


const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const suggestions = document.getElementById('suggestions');
const inputField = document.getElementById('user-input');
const container = document.querySelector('.container');

let userAnswers = null
let currentQuestion = null;
let awaitingResponse = false;
let userText = "";

// const socket = new WebSocket("ws://localhost:8080/movie-agent-qa");
const socket = new WebSocket("wss://auto-gens.com/movie-agent-qa");

socket.onopen = () => {
    addMessage("Привет! Опиши, какой фильм ты хочешь посмотреть (жанр, атмосфера, примеры и т.д.)", "bot");
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "question") {
        currentQuestion = data;
        awaitingResponse = true;
        addMessage(data.question, "bot");
    } else if (data.type === "search") {
        userAnswers = {
            query: data.query || "",
            genres: data.genres || [],
            atmospheres: data.atmospheres || [],
            start_year: data.start_year || 1900,
            end_year: data.end_year || 2025
        };
        awaitingResponse = false;
    } else if (data.type === "done") {
        awaitingResponse = false;

        sessionStorage.setItem('movieCategories', JSON.stringify(userAnswers.genres));
        sessionStorage.setItem('movieAtmospheres', JSON.stringify(userAnswers.atmospheres));
        sessionStorage.setItem('yearStart', userAnswers.start_year);
        sessionStorage.setItem('yearEnd', userAnswers.end_year);
        sessionStorage.setItem('movieDescription', userAnswers.query);
        sessionStorage.setItem('movieSuggestion', "");
        sessionStorage.setItem('movieSearch', "");

        window.location.href = "matching.html";
    } else if (data.error) {
        awaitingResponse = false;
        console.error("Ошибка:", data.error);
    }
};

socket.onerror = (err) => {
    console.error("WebSocket error:", err);
};

socket.onclose = (event) => {
    console.warn("Соединение с WebSocket закрыто:", event.reason || "без причины");
    addMessage("⚠️ Соединение потеряно. Пожалуйста, перезагрузите страницу.", "bot");
};

function scrollChatToBottom() {
    setTimeout(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
    }, 0);
}

function addMessage(text, sender, suggestionsList = []) {
    const message = document.createElement("div");
    message.classList.add("message", sender);
    chatBox.appendChild(message);
    scrollChatToBottom();

    if (sender === "user") {
        message.innerHTML = text.replace(/\n/g, "<br>");
        scrollChatToBottom();
        return;
    }

    let index = 0;
    const typingSpeed = 30;

    const interval = setInterval(() => {
        if (index < text.length) {
            const char = text[index] === '\n' ? '<br>' : text[index];
            message.innerHTML += char;
            index++;
            scrollChatToBottom();
        } else {
            clearInterval(interval);

            if (suggestionsList.length > 0) {
                let suggestionsContainer = chatBox.querySelector(".suggestions");

                if (!suggestionsContainer) {
                    suggestionsContainer = document.createElement("div");
                    suggestionsContainer.classList.add("suggestions");
                    message.appendChild(suggestionsContainer);
                } else {
                    suggestionsContainer.innerHTML = "";
                }

                suggestionsList.forEach((suggestion) => {
                    const button = document.createElement("button");
                    button.classList.add("suggestion-button");
                    button.innerText = suggestion;
                    suggestionsContainer.appendChild(button);
                });

                scrollChatToBottom();
            }
        }
    }, typingSpeed);
}

function showNoStarsModal() {
    const modal = document.getElementById("no-stars-modal");
    modal.classList.remove("hidden");

    async function waitForStarsAfterPayment(retryLimit = 20, interval = 1500) {
        for (let i = 0; i < retryLimit; i++) {
            try {
                const response = await apiPost("/user-init", { user_id: userId }, initData);
                if (response.balance && response.balance > 0) {
                    document.getElementById("no-stars-modal").classList.add("hidden");
                    awaitingResponse = false;
                    awaitingRequest = true;
                    await fetchStreamingResponse();
                    return;
                }
            } catch (e) {
                console.warn("Ошибка при проверке баланса:", e);
            }
            await new Promise(resolve => setTimeout(resolve, interval));
        }
        alert("Похоже, оплата не была завершена. Попробуйте снова.");
        window.location.href = "profile.html";
    }

    document.getElementById("modal-buy-stars").onclick = async () => {
        await handleDonate();
        await waitForStarsAfterPayment();
    };

    document.getElementById("modal-cancel").onclick = () => {
        window.location.href = "profile.html";
    };
}

function handleUserInput() {
    if (!userText || socket.readyState !== WebSocket.OPEN) return;

    removeCurrentSuggestions();
    addMessage(userText, "user");
    userInput.value = "";
    awaitingResponse = true;

     if (!currentQuestion) {
        socket.send(JSON.stringify({query: userText}));
     } else {
        socket.send(JSON.stringify({answer: userText}));
        currentQuestion = null;
    }
}

function removeCurrentSuggestions() {
    const allSuggestions = chatBox.querySelectorAll('.suggestions');
    if (allSuggestions.length > 0) {
        allSuggestions[allSuggestions.length - 1].remove();
    }
}

chatBox.addEventListener('click', (e) => {
    if (e.target.classList.contains('suggestion-button')) {
        userText = e.target.innerText;
        e.target.closest('.suggestions').innerHTML = '';
        handleUserInput()
    }
});

function handleInputEvent(e) {
    if (e.type === 'click' || (e.type === 'keypress' && e.key === 'Enter')) {
        userText = userInput.value.trim();
        if (!userText) return;
        handleUserInput();
    }
}

document.addEventListener('touchstart', (event) => {
    const input = document.getElementById('user-input');
    if (input && !input.contains(event.target)) {
        input.blur();
    }
});

sendButton.addEventListener('click', handleInputEvent);
userInput.addEventListener('keypress', handleInputEvent);

inputField.addEventListener('focus', () => {
    container.classList.add('keyboard-open');
});

inputField.addEventListener('blur', () => {
    container.classList.remove('keyboard-open');
});

document.addEventListener("DOMContentLoaded", async () => {
    backButton("index.html");
    initBottomNav();
    void logEvent(userId, "open", initData);
})