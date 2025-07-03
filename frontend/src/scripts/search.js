import {initData, tgBackButton, backButton, userId} from "../common/telegram.js";
import { logEvent } from "../common/api.js";
import { initBottomNav } from "../common/i18n.js";

document.addEventListener('touchstart', (event) => {
    const customInput = document.getElementById('movie-input');
    if (event.target !== customInput && !customInput.contains(event.target)) {
        customInput.blur();
    }
});

document.getElementById('movie-submit').addEventListener('click', async () => {
    const movieInput = document.getElementById('movie-input').value;
    if (movieInput.trim()) {
        sessionStorage.setItem('movieSearch', movieInput);
        sessionStorage.setItem('movieCategories', "[]");
        sessionStorage.setItem('movieAtmospheres', "[]");
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
    initBottomNav();
    void logEvent(userId, "open", initData);
});