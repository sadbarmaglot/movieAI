import { apiPost, logEvent } from "../common/api.js";
import {tg, initData, userId, tgBackButton, vibrateOnClick, fetchUserBalance} from "../common/telegram.js";

if (initData && initData !== "test") {
    tg.ready();
    tg.expand();
    tg.requestFullscreen();
    tg.disableVerticalSwipes();
}

const startParam = tg.initDataUnsafe?.start_param;

function parseStartParam(param) {
    const result = {};
    if (!param) return result;

    const movieMatch = param.match(/movie_(\d+)/);
    const refMatch = param.match(/ref_(\d+)/);

    if (movieMatch) result.movieId = parseInt(movieMatch[1]);
    if (refMatch) result.refUserId = parseInt(refMatch[1]);

    return result;
}

async function handleStartParam() {
    const result = parseStartParam(startParam);
    const localMovieId = sessionStorage.getItem("movieID");

    if (result.refUserId) {
        try {
            await apiPost("/referral", {
                user_id: userId,
                referred_by: result.refUserId
            }, initData);
        } catch (error) {
            console.warn("Referral failed:", error);
        }
    }

    if (result.movieId && !localMovieId) {
        sessionStorage.setItem("movieID", result.movieId);
        window.location.href = "movie_page.html";
    }
}

function attachEventListeners() {
    document.querySelectorAll(".card").forEach((card) => {
        const href = card.dataset.href;
        card.addEventListener("click", async () => {
            vibrateOnClick();
            const action = href.replace(".html", "") + "_card";
            await logEvent(userId, action, initData, null);
            window.location.href = href;
        });
    });

    document.querySelectorAll(".nav-button").forEach((btn) => {
        const href = btn.dataset.href;
        btn.addEventListener("click", async () => {
            vibrateOnClick();
            const action = href.replace(".html", "") + "_tab";
            await logEvent(userId, action, initData, null);
            window.location.href = href;
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    tgBackButton.hide();
    await logEvent(userId, "open", initData, startParam);
    attachEventListeners();
    await handleStartParam();
    await fetchUserBalance();
});
