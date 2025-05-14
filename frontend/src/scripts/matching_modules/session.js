export function saveMovieSession({ currentMovie, movieQueue, excludedMovies, favoriteMovies, storedData, hasCriteria, endOfMatching }) {
    console.log("💾 saveMovieSession()", { hasCriteria, endOfMatching });

    if (!hasCriteria || endOfMatching) {
        console.warn("🚫 Нет данных — не сохраняем сессию");
        return;
    }

    try {

        localStorage.setItem("currentMovie", JSON.stringify(currentMovie));
        localStorage.setItem("movieQueue", JSON.stringify(movieQueue));
        localStorage.setItem("excludedMovies", JSON.stringify(excludedMovies));
        localStorage.setItem("favoriteMovies", JSON.stringify(favoriteMovies));
        localStorage.setItem("storedData", JSON.stringify(storedData));
    } catch (e) {
        console.error("❌ Ошибка при сохранении в localStorage:", e);
    }
}

export function restoreMovieSession() {
    try {
        const savedQueue = JSON.parse(localStorage.getItem("movieQueue") || "[]");
        const savedCurrent = JSON.parse(localStorage.getItem("currentMovie") || "null");
        const savedExcluded = JSON.parse(localStorage.getItem("excludedMovies") || "[]");
        const savedFavorites = JSON.parse(localStorage.getItem("favoriteMovies") || "[]");
        const savedStoredData = JSON.parse(localStorage.getItem("storedData") || "{}");

        return {
            movieQueue: Array.isArray(savedQueue) ? savedQueue : [],
            currentMovie: savedCurrent || null,
            excludedMovies: Array.isArray(savedExcluded) ? savedExcluded : [],
            favoriteMovies: Array.isArray(savedFavorites) ? savedFavorites : [],
            storedData: savedStoredData || {}
        };
    } catch (e) {
        console.warn("Не удалось восстановить сессию:", e);
        return {
            movieQueue: [],
            currentMovie: null,
            excludedMovies: [],
            favoriteMovies: [],
            storedData: {}
        };
    }
}

export function clearOldSession() {
    localStorage.removeItem("movieQueue");
    localStorage.removeItem("currentMovie");
    localStorage.removeItem("excludedMovies");
    localStorage.removeItem("favoriteMovies");
    localStorage.removeItem("storedData");
}

export function clearCurentSession() {
    sessionStorage.removeItem("movieCategories");
    sessionStorage.removeItem("movieAtmospheres");
    sessionStorage.removeItem("movieDescription");
    sessionStorage.removeItem("movieSuggestion");
    sessionStorage.removeItem("movieSearch");
    sessionStorage.removeItem("userAnswers");
}

function normalizeData(obj) {
    return Object.fromEntries(
        Object.entries(obj)
            .filter(([_, v]) => v !== null && v !== "" && v !== undefined)
            .sort(([a], [b]) => a.localeCompare(b))
    );
}

export function isStoredDataDifferent(currentStoredData) {
    try {
        const previousStored = JSON.parse(localStorage.getItem("storedData") || "{}");
        const current = normalizeData(currentStoredData);
        const previous = normalizeData(previousStored);
        return JSON.stringify(previous) !== JSON.stringify(current);
    } catch (e) {
        console.warn("⚠️ Не удалось сравнить storedData:", e);
        return true;
    }
}

