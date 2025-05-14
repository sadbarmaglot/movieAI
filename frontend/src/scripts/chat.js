import {apiPost, apiPostStream, logEvent} from "../common/api.js";
import {userId, initData, vibrateOnClick, backButton, handleDonate} from "../common/telegram.js";

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const suggestions = document.getElementById('suggestions');

let userAnswers = [];
let questionQueue = [];
let awaitingResponse = false;
let awaitingRequest = true;
let firstQuestionAnswered = false;
let userText = "";
let useDescription = false;
let currentQuestion = {
    question: "Привет!\n\n" +
        "Давай подберём фильм.\n\n" +
        "Как тебе удобнее начать?\n\n" +
        "Опиши, какой фильм хочешь посмотреть или я могу сразу задать тебе несколько наводящих вопросов"
};

const startOptions = [
  "Опишу самостоятельно",
  "Задай мне вопросы"
];

addMessage(currentQuestion.question, "bot", startOptions);

function scrollChatToBottom(){
    chatBox.scrollTop = chatBox.scrollHeight;
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

async function fetchStreamingResponse() {
    if (!awaitingRequest) return;

    awaitingRequest = false;

    function handleNewQuestion(question) {
        if (question) {
            questionQueue.push(question);
            if (!awaitingResponse) {
                showNextQuestion();
            }
        }
    }

    function handleStreamComplete() {}

    function handleStreamError(error) {

        const status = error?.status;
        const detail = error?.detail || error?.message || error?.toString() || "Неизвестная ошибка";
        const lowerDetail = detail.toLowerCase();

        const ignoredErrors = [
            "network error",
            "Failed to fetch",
            "The user aborted a request",
            "ERR_QUIC_PROTOCOL_ERROR",
            "Load Failed"
        ];

         if (ignoredErrors.some(msg => lowerDetail.includes(msg))) {
            console.warn("⚠️ Сетевая ошибка проигнорирована:", detail);
            return;
        }

        if (status === 403 && lowerDetail.includes("звёзд")) {
            awaitingRequest = true;
            showNoStarsModal();
            return;
        }
    }

    await apiPostStream(
        "/questions-streaming",
        {user_id: userId},
        handleNewQuestion,
        handleStreamComplete,
        handleStreamError,
        initData
    );

    awaitingRequest = false;

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

function showNextQuestion() {
    if (questionQueue.length > 0) {
        awaitingResponse = true;
        const nextQuestion = questionQueue.shift();
        currentQuestion.question = nextQuestion.question
        addMessage(nextQuestion.question, "bot", nextQuestion.suggestions || []);
    } else if (!awaitingRequest) {
        sessionStorage.setItem('userAnswers', JSON.stringify(userAnswers));
        sessionStorage.setItem('movieDescription', "");
        sessionStorage.setItem('movieCategories', "[]");
        sessionStorage.setItem('movieAtmospheres', "[]");
        sessionStorage.setItem('movieSearch', "");
        sessionStorage.setItem('movieSuggestion', "");
        sessionStorage.setItem('yearStart', "");
        sessionStorage.setItem('yearEnd', "");

        window.location.href = 'matching.html';
    }
}

function useDescriptionMatching() {
    sessionStorage.setItem('movieDescription', userText);
    sessionStorage.setItem('userAnswers', "");
    sessionStorage.setItem('movieCategories', "[]");
    sessionStorage.setItem('movieAtmospheres', "[]");
    sessionStorage.setItem('movieSearch', "");
    sessionStorage.setItem('movieSuggestion', "");
    sessionStorage.setItem('yearStart', "");
    sessionStorage.setItem('yearEnd', "");

    window.location.href = 'matching.html';
}


function handleUserInput() {

    removeCurrentSuggestions();
    addMessage(userText, "user");
    userInput.value = "";

    if (!firstQuestionAnswered) {
        firstQuestionAnswered = true;

        if (userText === "Опишу самостоятельно") {
            useDescription = true;
            currentQuestion = {
                question: "Отлично! Опиши, какой фильм ты хочешь посмотреть (жанр, атмосфера, пример и т.д.)"
            };
            addMessage(currentQuestion.question, "bot");
            return;
        } else if (userText === "Задай мне вопросы") {
            currentQuestion.answer = userText
            userAnswers.push(currentQuestion)
            currentQuestion = {}
            awaitingResponse = false;
            fetchStreamingResponse();
            return
        } else {
            useDescription = true;
            useDescriptionMatching();
            return;
        }
    }

    if (useDescription) {
        useDescriptionMatching();
        return;
    }

    currentQuestion.answer = userText
    userAnswers.push(currentQuestion)
    currentQuestion = {}
    awaitingResponse = false;
    showNextQuestion();
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

document.querySelectorAll(".nav-button").forEach((btn) => {
    const href = btn.getAttribute("onclick")?.match(/'(.+?)'/)?.[1];
    btn.removeAttribute("onclick");
    btn.addEventListener("click", () => {
        vibrateOnClick();
        if (href) { window.location.href = href; }
    });
});

sendButton.addEventListener('click', handleInputEvent);
userInput.addEventListener('keypress', handleInputEvent);

document.addEventListener("DOMContentLoaded", async () => {
    backButton("index.html");
    void logEvent(userId, "open", initData);
});