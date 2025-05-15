import { userLang } from "./telegram.js";
import { vibrateOnClick, initData, userId } from "./telegram.js";
import { logEvent } from "./api.js";

export const TEXTS = {
  en: {
    nav_search: "Search",
    nav_matching: "Matching",
    nav_favorites: "Favorites",
    nav_profile: "Profile",
  },
  ru: {
    nav_search: "Поиск",
    nav_matching: "Подбор",
    nav_favorites: "Избранное",
    nav_profile: "Профиль",
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