import { logEvent } from "../common/api.js";
import {
    tg,
    userId,
    initData,
    vibrateOnClick,
    handleDonate,
    fetchUserBalance,
    backButton,
    shareApp
} from "../common/telegram.js";
import { initBottomNav } from "../common/i18n.js";

function getInstallTipText() {
    const ua = navigator.userAgent.toLowerCase();
    if (ua.includes("iphone") || ua.includes("ipad")) {
        return `Если понравилось приложение, можно добавить на экран <br> «Домой»`;
    } else {
        return `Если понравилось приложение, можно <br> «Добавить на главный экран»`;
    }
}

async function setBalance() {
    const balanceEl = document.getElementById("balanceValue");
    balanceEl.textContent = "...";
    const response = await fetchUserBalance();
    if (response && response.balance !== undefined) {
        balanceEl.textContent = response.balance;
    }
}

function animateBalanceUpdate(from, to) {
    const el = document.getElementById("balanceValue");
    const duration = 1000;
    const frameRate = 30;
    const totalFrames = Math.round(duration / (1000 / frameRate));
    let frame = 0;

    const interval = setInterval(() => {
        frame++;
        const progress = frame / totalFrames;
        const current = Math.round(from + (to - from) * progress);
        el.textContent = current;

        if (frame >= totalFrames) {
            clearInterval(interval);
            el.textContent = to;
        }
    }, 1000 / frameRate);
}

async function handleDonateClick() {
    await logEvent(userId, "donateCard", initData, null);
    await handleDonate();
    setTimeout(async () => {
        const oldBalance = parseInt(document.getElementById("balanceValue").textContent) || 0;
        const response = await fetchUserBalance();
        if (response && response.balance !== undefined) {
            animateBalanceUpdate(oldBalance, response.balance);
        }
    }, 5000);
}

function setUserInfo() {
    try {
        const user = tg.initDataUnsafe.user;
        if (!user) return;

        const name = user.first_name || "Пользователь";
        const photo = user.photo_url;

        document.getElementById("userName").textContent = name;
        if (photo) {
            document.getElementById("userAvatar").src = photo;
        }
    } catch (e) {
        console.error("Ошибка при получении user info:", e);
    }
}

function showTooltip(message = "Готово!", showSubtext = true) {
    const tooltip = document.getElementById("shareTooltip");
    const mainText = tooltip.querySelector('.main-text');
    const subText = tooltip.querySelector('.tooltip-subtext');

    if (mainText) mainText.textContent = message;
    if (subText) subText.style.display = showSubtext ? "block" : "none";

    tooltip.classList.add("show");

    setTimeout(() => {
        tooltip.classList.remove("show");
    }, 5000);
}

function attachEventListeners() {
    const donateButton = document.getElementById("donateCard")?.querySelector(".card-button");
    if (donateButton) {
        donateButton.removeEventListener("click", handleDonateClick);
        donateButton.addEventListener("click", handleDonateClick);
    }

    const shareAppButton = document.getElementById("shareCard")?.querySelector(".card-button");
    if (shareAppButton) {
        shareAppButton.removeEventListener("click", shareApp);
        shareAppButton.addEventListener("click", async () => {
            await logEvent(userId, "shareCard", initData, null);
            const success = await shareApp();
            if (success) {
                showTooltip("Ссылка отправлена!", success);
            } else {
                showTooltip("Не удалось отправить ссылку", success);
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    backButton("index.html");
    initBottomNav();
    await logEvent(userId, "open", initData);
    if (!sessionStorage.getItem("tipShown")) {
        document.getElementById("tip-text").innerHTML = getInstallTipText();
        const tipEl = document.getElementById("telegram-tip");
        if (tipEl) {
            tipEl.style.display = "block";
            sessionStorage.setItem("tipShown", "1");

            setTimeout(() => {
                tipEl.remove();
            }, 10000);
        }
    }
    attachEventListeners();
    setUserInfo();
    await setBalance();
});