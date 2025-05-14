import {initData, tgBackButton, vibrateOnClick, backButton, userId} from "../common/telegram.js";
import {logEvent} from "../common/api.js";

document.addEventListener('touchstart', (event) => {
    const customInput = document.getElementById('movie-input');
    if (event.target !== customInput && !customInput.contains(event.target)) {
        customInput.blur();
    }
});

document.querySelectorAll(".nav-button").forEach((btn) => {
    const href = btn.getAttribute("onclick")?.match(/'(.+?)'/)?.[1];
    btn.removeAttribute("onclick");
    btn.addEventListener("click", () => {
        vibrateOnClick();
        if (href) {
            window.location.href = href;
            setTimeout(() => {
                tgBackButton.hide();
                }, 50
            );
        }
    });
});

document.getElementById('movie-submit').addEventListener('click', async () => {
    const movieInput = document.getElementById('movie-input').value;
    if (movieInput.trim()) {
        sessionStorage.setItem('movieSearch', movieInput);
        sessionStorage.setItem('movieCategories', "[]");
        sessionStorage.setItem('movieAtmospheres', "[]");
        sessionStorage.setItem('userAnswers', "");
        sessionStorage.setItem('movieSuggestion', "");
        sessionStorage.setItem('movieDescription', "");
        sessionStorage.setItem('yearStart', "");
        sessionStorage.setItem('yearEnd', "");

        window.location.href = 'matching.html';

        setTimeout(() => {
            tgBackButton.hide();
            }, 50
        );
    } else {
        alert("Пожалуйста, введите название фильма");
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    backButton("index.html");
    void logEvent(userId, "open", initData);
});