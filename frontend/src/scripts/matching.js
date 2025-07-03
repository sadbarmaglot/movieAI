import {
    apiGet,
    apiPost,
    apiPostStream,
    apiWebSocketStream,
    fetchFavorites,
    addToFavorites,
    addToSkipped,
    logEvent
} from "../common/api.js";
import {
    userId,
    initData,
    vibrateOnClick,
    showLoader,
    hideLoader,
    shareButton,
    handleDonate,
    backButton
} from "../common/telegram.js";
import {
    DEFAULT_POSTER,
    createMovieCard,
    updateMovieRatings,
    updateMovieDescription,
    updateMovieGenres,
    updateKinopoiskLink,
    updateGlobalMovieTitles
} from "./matching_modules/movie_card.js"
import {
    saveMovieSession,
    restoreMovieSession,
    clearOldSession,
    clearCurentSession,
    isStoredDataDifferent
} from "./matching_modules/session.js"
import { initBottomNav } from "../common/i18n.js";
import { attachCardEvents } from "./matching_modules/swiper.js"

const storedData = [
    'movieCategories',
    'movieAtmospheres',
    'movieDescription',
    'movieSuggestion',
    'movieSearch',
    'yearStart',
    'yearEnd'
].reduce((acc, key) => {
    acc[key] = sessionStorage.getItem(key);
    return acc;
    }, {});

const hasCriteria =
    storedData["movieCategories"] ||
    storedData["movieAtmospheres"] ||
    storedData["movieDescription"] ||
    storedData["movieSuggestion"] ||
    storedData["movieSearch"]

const isSearchMode = Boolean(storedData["movieSearch"]);

const yearStart = parseInt(storedData["yearStart"]) || 1900;
const yearEnd = parseInt(storedData["yearEnd"]) || 2025;
const sourceMovie = parseInt(storedData["movieSuggestion"]) || null;
const query = storedData["movieDescription"] || null;

let favoriteMovies = [];
let excludedMovies = [];
let movieQueue = []
let currentMovie = null

const MatchingPhase = {
    IDLE: 'idle',
    STREAMING: 'streaming',
    TRANSITION: 'transition',
    WAITING_USER: 'waiting_user',
    DONE: 'done',
    ERROR: 'error'
};

let currentPhase = MatchingPhase.IDLE;

function setPhase(phase) {
    currentPhase = phase;
    console.log(`📦 [Phase] -> ${phase}`);
}

function is(phase) {
    return currentPhase === phase;
}

let pendingAutoShow = false;
let hasSession = localStorage.getItem("currentMovie");

function tryAutoShowIfPossible(retry = true) {
    if (pendingAutoShow && movieQueue.length > 0) {
        if (!is(MatchingPhase.TRANSITION)) {
            pendingAutoShow = false;
            console.log("🚀 Показываем отложенный фильм из tryAutoShowIfPossible");
            showNextMovieUnified();
        } else if (retry) {
            console.log("⏳ Ждём завершения transition (retry=true), проверим позже");
            setTimeout(() => tryAutoShowIfPossible(true), 200);
        }
    }
}

async function fetchStreamingResponse() {
    if (is(MatchingPhase.STREAMING)) return;

    setPhase(MatchingPhase.STREAMING);
    let firstMovieFromThisBatchShown = false;

    function isInRangeInclusive(num, a, b) {
        if (a === null || b === null) return true;
        return num >= a && num <= b;
    }

    function handleNewMovie(movie) {
        console.log("🎥 Получен фильм:", movie.title_alt);
        const alreadyShown = movieQueue.some(m => m.movie_id === movie.movie_id);
        const isValid = !excludedMovies.includes(movie.movie_id) &&
                        !favoriteMovies.some(f => f.movie_id === movie.movie_id) &&
                        isInRangeInclusive(movie.year, yearStart, yearEnd) &&
                        !alreadyShown;

        if (!isValid) return;

        movieQueue.push(movie);
        hideLoader();

        if (!firstMovieFromThisBatchShown) {
            if (!is(MatchingPhase.TRANSITION)) {
                firstMovieFromThisBatchShown = true;
                pendingAutoShow = false;
                console.log("✅ Показываем фильм из handleNewMovie");
                showNextMovieUnified();
            } else {
                console.log("⏳ Автопоказ отложен — transition в процессе");
                pendingAutoShow = true;
                tryAutoShowIfPossible(true);
            }
        }

        if (pendingAutoShow && movieQueue.length > 0 && !is(MatchingPhase.TRANSITION)) {
            tryAutoShowIfPossible(true);
        }
    }

    function handleStreamComplete() {
        const addedMovies = movieQueue.length > 0;

        if (!addedMovies) {
            setPhase(MatchingPhase.DONE);
            hideLoader();
            alert("Фильмы закончились. Попробуйте задать другой запрос.");
            clearOldSession();
            clearCurentSession();
            window.location.href = storedData["movieSuggestion"]
                ? "favorites.html"
                : storedData["movieCategories"]
                ? "category.html"
                : "chat.html";
            return;
        }

        setPhase(MatchingPhase.WAITING_USER);
        hideLoader();
        tryAutoShowIfPossible(true);
    }

    function handleStreamError(error) {
        setPhase(MatchingPhase.ERROR);
        console.error("❌ Ошибка стрима:", error);

        hideLoader();

        const detail = (error?.detail || error?.message || error?.toString() || "").toLowerCase();
        const ignored = ["network error", "failed to fetch", "aborted", "quic", "load failed"];

        if (ignored.some(msg => detail.includes(msg))) {
            console.warn("⚠️ Сетевая ошибка проигнорирована:", detail);
            return;
        }

        if (error?.status === 403 && detail.includes("звёзд")) {
            showNoStarsModal();
        }
    }

    const body = {
        user_id: userId,
        action: query ? "movie_agent_streaming" : sourceMovie ? "similar_movie_streaming" : "movie_wv_streaming",
        source_kp_id: sourceMovie,
        movie_name: storedData["movieSearch"],
        query: query,
        genres: JSON.parse(storedData["movieCategories"] || "[]"),
        atmospheres: JSON.parse(storedData["movieAtmospheres"] || "[]"),
        start_year: yearStart,
        end_year: yearEnd
    };

    await apiWebSocketStream(
        "/movie_streaming-ws",
        body,
        handleNewMovie,
        handleStreamComplete,
        handleStreamError,
        initData
    );
}

function handleAutoShowAfterUserAction() {
    if (movieQueue.length === 0) {
        pendingAutoShow = true;

        if (is(MatchingPhase.STREAMING)) {
            showLoader();
            console.log("🔄 Ожидаем фильм из стрима (handleAutoShowAfterUserAction)");
        } else {
            console.log("🎯 Стрим не идёт — запускаем его (handleAutoShowAfterUserAction)");
            void waitForNewMovies();
        }
    }
}

function updateMovieInfo(card, movie) {
    updateMovieRatings(card, movie);
    updateMovieDescription(card, movie);
    updateMovieGenres(card, movie);
    updateKinopoiskLink(card, movie);
    updateGlobalMovieTitles(movie);
}

function preloadNextPoster() {
    if (movieQueue.length === 0) return;

    const nextMovie = movieQueue[0];
    const url = nextMovie.poster_url;

    if (!url) return;

    const img = new Image();
    img.src = url;
}

let transitionLock = Promise.resolve();

function showNextMovieUnified() {
    transitionLock = transitionLock.then(async () => {
        if (is(MatchingPhase.TRANSITION)) {
            console.log("⏸ Переход уже в процессе — игнорируем вызов");
            return;
        }

        setPhase(MatchingPhase.TRANSITION);

        try {
            await _showNextMovieUnified();
        } catch (e) {
            console.error("❌ Ошибка в showNextMovieUnified:", e);
            setPhase(MatchingPhase.ERROR);
        }

        setPhase(MatchingPhase.WAITING_USER);

        if (pendingAutoShow && movieQueue.length > 0 && is(MatchingPhase.WAITING_USER)) {
            console.log("🔁 Отложенный автошоу — вызываем showNextMovieUnified снова");
            tryAutoShowIfPossible();
        }
    });

    return transitionLock;
}

async function _showNextMovieUnified() {
    console.log("🔁 [showNextMovieUnified] Старт, очередь:", movieQueue.length);

    if (movieQueue.length === 0) {
        console.log("🛑 Нет фильмов в очереди");

        if (isSearchMode) {
            alert("Фильмы закончились. Попробуйте задать другой запрос.");
            window.location.href = "search.html";
        } else {
            await waitForNewMovies();
        }

        return;
    }

    currentMovie = movieQueue.shift();
    console.log(`🎬 Показываем: ${currentMovie.title_alt}`);

    const movieContainer = document.getElementById('movie-container');
    if (movieContainer.style.display === 'none') {
        movieContainer.style.display = 'flex';
    }

    const oldCard = movieContainer.querySelector('.movie-card');
    const newCard = createMovieCard(currentMovie);

    newCard.querySelector('.card-inner')?.addEventListener('click', vibrateOnClick);
    newCard.style.opacity = '0';

    movieContainer.insertBefore(newCard, movieContainer.firstChild);

    updateMovieInfo(newCard, currentMovie);
    document.getElementById('movie-container').setAttribute("style", `background: ${currentMovie.background_color} !important;`);

    attachCardEvents(newCard, currentMovie, {
        onLike: async (movie) => {
            void logEvent(userId, "like", initData);

            favoriteMovies = await addToFavorites(userId, movie, favoriteMovies, initData);

            const favBtn = document.getElementById('favorite-button');
            favBtn.classList.add('pulse');
            setTimeout(() => favBtn.classList.remove('pulse'), 200);

            if (movieQueue.length === 0) {
                pendingAutoShow = true;
                if (!is(MatchingPhase.STREAMING)) {
                    waitForNewMovies();
                }
            }
        },
        onSkip: async (movie) => {
            void logEvent(userId, "skip", initData);

            if (!isSearchMode) {
                excludedMovies.push(movie.movie_id);
                await addToSkipped(userId, movie, initData);
            }

            const skipBtn = document.getElementById('skip-button');
            skipBtn.classList.add('pulse');
            setTimeout(() => skipBtn.classList.remove('pulse'), 200);

            if (movieQueue.length === 0) {
                pendingAutoShow = true;
                if (!is(MatchingPhase.STREAMING)) {
                    waitForNewMovies();
                }
            }
        },
        onTransitionRequest: showNextMovieUnified
    });

    if (oldCard) movieContainer.removeChild(oldCard);

    const img = newCard.querySelector('#movie-poster');
    img.loading = 'eager';
    img.decoding = 'sync';
    img.src = currentMovie.poster_url || DEFAULT_POSTER;

    const posterReady = new Promise(resolve => {
        if (img.complete) resolve();
        img.onload = resolve;
            img.onerror = () => {
                img.src = DEFAULT_POSTER;
                resolve();
            };
    });

    const transitionDone = new Promise(resolve => {
        if (oldCard && (oldCard.classList.contains('fly-left') || oldCard.classList.contains('fly-right'))) {
            // oldCard.addEventListener('transitionend', () => {
            // });
            let done = false;

            const onTransitionEnd = () => {
                if (!done) {
                    done = true;
                    oldCard.remove();
                    resolve();
                }
            };

            const timeout = setTimeout(onTransitionEnd, 200);

            oldCard.addEventListener('transitionend', () => {
                clearTimeout(timeout);
                onTransitionEnd();
            }, {once: true});

        } else {
            if (oldCard) oldCard.remove();
            resolve();
        }
    });

    console.log("⏳ Ожидаем загрузку постера и завершение transition");
    await Promise.all([posterReady, transitionDone]);

    newCard.classList.add('animate-in');
    newCard.style.opacity = '1';
    preloadNextPoster();
}

async function waitForNewMovies() {
    if (movieQueue.length > 0 || is(MatchingPhase.TRANSITION)) {
        return;
    }

    showLoader();

    if (!is(MatchingPhase.STREAMING)) {
        console.log("📭 Очередь пуста и стрим не идёт — запускаем fetchStreamingResponse");
        await fetchStreamingResponse();
    } else {
        console.log("⚙️ Стрим уже идёт, ждём завершения");
        pendingAutoShow = true;
    }
}

document.getElementById('favorite-button').addEventListener('click', async () => {
    vibrateOnClick();
    void logEvent(userId, "like_button", initData);

    favoriteMovies = await addToFavorites(userId, currentMovie, favoriteMovies, initData);

    if (pendingAutoShow) {
        pendingAutoShow = false;
    }

    handleAutoShowAfterUserAction();
    showNextMovieUnified();
});

document.getElementById('skip-button').addEventListener('click', async() => {
    vibrateOnClick();
    void logEvent(userId, "skip_button", initData);

    if (!isSearchMode) {
        excludedMovies.push(currentMovie.movie_id);
        await addToSkipped(userId, currentMovie, initData);
    }

    if (pendingAutoShow) {
        pendingAutoShow = false;
    }

    handleAutoShowAfterUserAction();
    showNextMovieUnified();
});

document.getElementById('share-button').addEventListener('click', async () => {
    vibrateOnClick();
    void logEvent(userId, "share", initData);
    const movieID = currentMovie.movie_id
    await shareButton(movieID);
});

window.addEventListener('beforeunload', () => {
    saveMovieSession({
        currentMovie,
        movieQueue,
        excludedMovies,
        favoriteMovies,
        storedData,
        hasCriteria,
        endOfMatching: is(MatchingPhase.DONE)
    });
});

window.addEventListener('pagehide', () => {
    saveMovieSession({
        currentMovie,
        movieQueue,
        excludedMovies,
        favoriteMovies,
        storedData,
        hasCriteria,
        endOfMatching: is(MatchingPhase.DONE)
    });
});

function initializeFromSession() {
    const restored = restoreMovieSession();
    movieQueue = restored.movieQueue;
    excludedMovies = restored.excludedMovies;
    currentMovie = restored.currentMovie;
    favoriteMovies = restored.favoriteMovies;
    Object.assign(storedData, restored.storedData);
}

async function initializeMatching() {
    if (hasSession && isStoredDataDifferent(storedData)) {
        clearOldSession();
        hasSession = false;
        currentMovie = null;
    }

    if (!hasSession && !hasCriteria) {
        alert("Упс, нет фильмов для подбора, попробуй сформировать запрос")
        window.location.href = "index.html";
        return;
    }

    initializeFromSession();

    if (!hasSession && hasCriteria) {
        showLoader();
        fetchFavorites(userId, initData).then(result => {
            favoriteMovies = result;
            setPhase(MatchingPhase.IDLE);
            fetchStreamingResponse();
        });
    } else {
        if (currentMovie) {
            console.log("🔄 Восстановлен фильм из сессии:", currentMovie.title_alt);

            if (movieQueue.length === 0 && !is(MatchingPhase.STREAMING)) {
                console.log("🟢 Очередь пуста после восстановления — вызываем waitForNewMovies()");
                showLoader();
                await waitForNewMovies();
                tryAutoShowIfPossible();
            } else {
                showCurrentMovieFromSession(currentMovie);
            }
        } else {
            console.warn("⚠️ currentMovie не найден в сессии — покажем следующий");
            showNextMovieUnified();
        }
    }
}

async function showCurrentMovieFromSession(movie) {
    const movieContainer = document.getElementById('movie-container');

    if (!movieContainer) return;

    if (movieContainer.style.display === 'none') {
        movieContainer.style.display = 'flex';
    }

    const oldCard = movieContainer.querySelector('.movie-card');
    if (oldCard) oldCard.remove();

    const card = createMovieCard(movie);

    card.querySelector('.card-inner')?.addEventListener('click', vibrateOnClick);

    card.style.opacity = '0';

    updateMovieInfo(card, movie);

    attachCardEvents(card, movie, {
            onLike: async (movie) => {
                void logEvent(userId, "like", initData);
                favoriteMovies = await addToFavorites(userId, movie, favoriteMovies, initData);

                const favBtn = document.getElementById('favorite-button');
                favBtn.classList.add('pulse');
                setTimeout(() => favBtn.classList.remove('pulse'), 200);

                handleAutoShowAfterUserAction();
            },
            onSkip: async (movie) => {
                void logEvent(userId, "skip", initData);
                if (!isSearchMode) {
                    excludedMovies.push(movie.movie_id);
                    await addToSkipped(userId, movie, initData);
                }

                const skipBtn = document.getElementById('skip-button');
                skipBtn.classList.add('pulse');
                setTimeout(() => skipBtn.classList.remove('pulse'), 200);

                handleAutoShowAfterUserAction();
            },
            onTransitionRequest: showNextMovieUnified
        });

    movieContainer.insertBefore(card, movieContainer.firstChild);

    movieContainer.setAttribute("style", `background: ${currentMovie.background_color} !important;`);

    const img = card.querySelector('#movie-poster');

    img.loading = 'eager';
    img.decoding = 'sync';

    img.src = currentMovie.poster_url || DEFAULT_POSTER;

     const posterReady = new Promise(resolve => {
        if (img.complete) resolve();
        img.onload = resolve;
            img.onerror = () => {
                img.src = DEFAULT_POSTER;
                resolve();
            };
    });

    await posterReady;
    card.classList.add('animate-in');
    card.style.opacity = '1';

    preloadNextPoster();
}

function showNoStarsModal() {
    const modal = document.getElementById("no-stars-modal");
    modal.classList.remove("hidden");

    setPhase(MatchingPhase.IDLE);

    async function waitForStarsAfterPayment(retryLimit = 20, interval = 1500) {
        for (let i = 0; i < retryLimit; i++) {
            try {
                const response = await apiPost("/user-init", { user_id: userId }, initData);
                if (response.balance && response.balance > 0) {
                    document.getElementById("no-stars-modal").classList.add("hidden");
                    setPhase(MatchingPhase.IDLE);
                    await waitForNewMovies();
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
        void logEvent(userId, "buy_stars", initData);
        await handleDonate();
        await waitForStarsAfterPayment();
    };

    document.getElementById("modal-cancel").onclick = async () => {
        void logEvent(userId, "cancel_buy_stars", initData);
        window.location.href = "profile.html";
    };
}

document.addEventListener('DOMContentLoaded', async () => {
    backButton("index.html");
    initBottomNav();
    void logEvent(userId, "open", initData);
    await initializeMatching();
});