import { apiPost } from "./api.js";

export const tg = window.Telegram?.WebApp || {
    initData: "test",
    MainButton: {
        text: "Test Button",
        show: () => console.log("Main button shown"),
        hide: () => console.log("Main button hidden"),
    },
    BackButton: {
    show: () => console.log("Back button shown"),
    hide: () => console.log("Back button hidden"),
    onClick: (cb) => console.log("Back button clicked"),
    },
    close: () => console.log("WebApp closed"),
};
export const tgBackButton = window.Telegram?.WebApp?.BackButton;
export const initData = window.Telegram?.WebApp?.initData || "test";

const langCode = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code || 'en';
export const userLang = langCode.startsWith('ru') ? 'ru' : 'en';

export let userId = 2
if (tg.initData && tg.initData !== "test") {
    userId = tg.initDataUnsafe?.user?.id
}

export function backButton(page) {
    if (initData !== "test") {
        tgBackButton.show();
        tgBackButton.onClick(() => {
            window.location.href = page;
            setTimeout(() => {
                tgBackButton.hide();
                }, 50);
        });
    }
}

export function vibrateOnClick() {
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred("medium");
    } else if ("vibrate" in navigator) {
        navigator.vibrate(50);
    }
}

export function showLoader() {
    document.getElementById('loader').style.display = 'flex';
}

export function hideLoader() {
    document.getElementById('loader').style.display = 'none';
}

export async function shareButton(movieID) {
    vibrateOnClick();
    const shareUrl = `https://auto-gens.com/preview/movie_${movieID}_ref_${userId}`;

    if (navigator.share) {
        try {
            await navigator.share({
                title: 'Рекомендую фильм!',
                url: shareUrl,
            });
            console.log("Контент успешно отправлен");
        } catch (error) {
            console.error("Ошибка при использовании Web Share API:", error);
        }
    } else {
        window.open(shareUrl, '_blank');
    }
}

export async function shareApp() {
    vibrateOnClick();
    const refLink = `https://t.me/MovieAI777_bot/WatchMe?startapp=ref_${userId}`;

    if (navigator.share) {
        try {
            await navigator.share({
                title: 'Попробуй приложение для подбора фильмов!',
                url: refLink,
            });
            console.log("Ссылка отправлена");
            return true;
        } catch (error) {
            console.error("Ошибка при использовании Web Share API:", error);
            return false;
        }
    } else {
        window.open(refLink, '_blank');
        return true;
    }
}

export async function fetchUserBalance() {
    try {
        return await apiPost("/user-init", { user_id: userId }, initData);
    } catch (e) {
        console.error("Ошибка при получении баланса", e);
    }
}

export async function handleDonate() {
    vibrateOnClick();
    if (userId && initData) {
        showLoader();
        try {
            const response = await apiPost("/create_invoice", { user_id: userId, amount: 100}, initData);
            if (response.ok) {
                tg.openInvoice(response.invoice_url);
            } else {
                alert("Ошибка: " + response.error);
            }
        } catch (error) {
            alert("Ошибка сети. Попробуйте снова.");
        } finally {
            hideLoader();
        }
    }
}