import { userLang } from "./telegram.js";
import { vibrateOnClick, initData, userId } from "./telegram.js";
import { logEvent } from "./api.js";

export const TEXTS = {
  en: {
    nav_search: "Search",
    nav_matching: "Matching",
    nav_favorites: "Favorites",
    nav_profile: "Profile",

    title_greeting: "Welcome to MovieAI!",
    subtitle_question: "How do you want to pick a movie?",

    card_category: "By category",
    card_chat: "In chat",
    card_title: "By title"
  },
  ru: {
    nav_search: "Поиск",
    nav_matching: "Подбор",
    nav_favorites: "Избранное",
    nav_profile: "Профиль",

    title_greeting: "Привет, киноман!",
    subtitle_question: "Как ты хочешь выбрать фильм?",

    card_category: "Категории",
    card_chat: "В чате",
    card_title: "Название"
  }
};

const t = (key) => TEXTS[userLang][key] || key;

export function initBottomNav() {
  const nav = document.querySelector(".bottom-nav");
  if (!nav) return;

  nav.querySelectorAll(".nav-button").forEach((btn) => {
    const label = btn.querySelector("div");
    const key = btn.dataset.key;
    if (label && key) label.textContent = t(key);
  });

  nav.querySelectorAll(".nav-button").forEach((btn) => {
    const href = btn.dataset.href;
    btn.addEventListener("click", async () => {
      vibrateOnClick();
      const action = href.replace(".html", "") + "_tab";
      await logEvent(userId, action, initData, null);
      window.location.href = href;
    });
  });

  nav.classList.add("ready");
}

export function initLocalization() {
  document.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    const value = t(key);
    el.textContent = value;
  });

  initBottomNav();
}
