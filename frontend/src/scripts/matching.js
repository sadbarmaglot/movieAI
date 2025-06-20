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
    'userAnswers',
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
    storedData["movieSearch"] ||
    storedData["userAnswers"];

const isSearchMode = Boolean(storedData["movieSearch"]);

const yearStart = parseInt(storedData["yearStart"]) || null;
const yearEnd = parseInt(storedData["yearEnd"]) || null;

let userAnswers
try {
    userAnswers = JSON.parse(storedData["userAnswers"] || "[]");
    if (!Array.isArray(userAnswers)) userAnswers = [];
} catch {
    userAnswers = [];
}

let favoriteMovies = [];
let excludedMovies = [];
let movieQueue = []
let currentMovie = null
let isTransitionInProgress = false;
let isFetching = false;
let hasSession = localStorage.getItem("currentMovie");
let endOfMatching = false;
let pendingAutoShow = false;
let isStreaming = false;

async function fetchStreamingResponse() {
    if (isStreaming) return;
    isStreaming = true;
    let firstMovieFromThisBatchShown = false;

    function isInRangeInclusive(num, a, b) {
        if (a === null || b === null) return true;
        return num >= a && num <= b;
    }
    function handleNewMovie(movie) {
        console.log("🎥 Получен фильм:", movie.title_alt);
        console.log("📦 handleNewMovie → isTransitionInProgress:", isTransitionInProgress);
        if (
            movie.title_alt &&
            movie.year &&
            !excludedMovies.includes(movie.title_alt)  &&
            !favoriteMovies.some(fav => fav.movie_id === movie.movie_id) &&
            isInRangeInclusive(movie.year, yearStart, yearEnd))
        {
            movieQueue.push(movie);
            hideLoader();

            if (!firstMovieFromThisBatchShown) {
                if (!isTransitionInProgress && !pendingAutoShow) {
                    firstMovieFromThisBatchShown = true;
                    console.log("✅ Показываем фильм из handleNewMovie");
                    showNextMovieUnified();
                    hideLoader();
                } else {
                    console.log("⏳ Автопоказ отложен — transition в процессе");
                    pendingAutoShow = true;
                }
            }
        }
    }

    function handleStreamComplete() {
        isStreaming = false;
        const didAddNewMovies = movieQueue.length > 0;
        console.log("🎬 handleStreamComplete → pendingAutoShow:", pendingAutoShow, "movieQueue.length:", movieQueue.length);

        if (!didAddNewMovies) {
            endOfMatching = true;
            hideLoader();
            alert("Фильмы закончились. Попробуйте задать другой запрос.");
            clearOldSession();
            clearCurentSession();
            if (storedData["movieSuggestion"]) {
                window.location.href = "favorites.html";
            } else if (storedData["movieCategories"]) {
                window.location.href = "category.html";
            } else {
                window.location.href = "chat.html";
            }
            return;
        }
        console.log("✅ Стрим завершён, фильмы добавлены, ждём взаимодействия пользователя");
        hideLoader();

        if (pendingAutoShow && movieQueue.length > 0) {
            const tryAutoShow = () => {
                if (!isTransitionInProgress) {
                    pendingAutoShow = false;
                    console.log("🚀 Показываем отложенный фильм из handleStreamComplete (таймер)");
                    showNextMovieUnified();
                } else {
                    console.log("⏳ Ждём завершения transition (таймер), проверим позже");
                    setTimeout(tryAutoShow, 200);
                }
            };
            tryAutoShow();
            //pendingAutoShow = false;
            //console.log("🚀 Показываем отложенный фильм из handleStreamComplete");
            //showNextMovieUnified();
        }
    }

    function handleStreamError(error) {
        isStreaming = false;
        console.error("Ошибка при загрузке фильмов:", error);
        hideLoader();

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
            showNoStarsModal();
            return;
        }
    }

    const useLegacyEndpoint =
        userAnswers.length > 0 ||
        Boolean(storedData["movieDescription"]) ||
        Boolean(storedData["movieSuggestion"]);

    if (useLegacyEndpoint) {
        const requestBody = {
            user_id: userId,
            chat_answers: userAnswers,
            genres: JSON.parse(storedData["movieCategories"] || "[]"),
            atmospheres: JSON.parse(storedData["movieAtmospheres"] || "[]"),
            description: storedData["movieDescription"],
            suggestion: storedData["movieSuggestion"],
            movie_name: storedData["movieSearch"],
            start_year: yearStart,
            end_year: yearEnd,
            exclude: Array.from(excludedMovies),
            favorites: favoriteMovies.map(movie => movie.title_alt)
        };

        await apiPostStream(
            "/movies-streaming",
            requestBody,
            handleNewMovie,
            handleStreamComplete,
            handleStreamError,
            initData
        );
    } else {
        const requestBody = {
            user_id: userId,
            genres: JSON.parse(storedData["movieCategories"] || "[]"),
            atmospheres: JSON.parse(storedData["movieAtmospheres"] || "[]"),
            movie_name: storedData["movieSearch"],
            start_year: yearStart,
            end_year: yearEnd,
        };
        await apiWebSocketStream(
            "/weaviate-streaming",
            requestBody,
            handleNewMovie,
            handleStreamComplete,
            handleStreamError,
            initData
            );
    }
}

function updateMovieInfo(card, movie) {
    updateMovieRatings(card, movie);
    updateMovieDescription(card, movie);
    updateMovieGenres(card, movie);
    updateKinopoiskLink(card, movie);
    updateGlobalMovieTitles(movie);
}

let transitionLock = Promise.resolve();

async function showNextMovieUnified() {
    transitionLock = transitionLock.then(() => _showNextMovieUnified());
    await transitionLock;
}

function preloadNextPoster() {
    if (movieQueue.length === 0) return;

    const nextMovie = movieQueue[0];
    const url = nextMovie.poster_url;

    if (!url) return;

    const img = new Image();
    img.src = url;
}

async function _showNextMovieUnified() {
    console.log("🔁 [showNextMovieUnified] Старт, очередь:", movieQueue.length, "transition:", isTransitionInProgress);
    if (isTransitionInProgress) return;
    isTransitionInProgress = true;

    try {
        console.log("🔁 START transition. Очередь:", movieQueue.length);

        if (movieQueue.length === 0) {
            console.log("🛑 Нет фильмов в очереди, переходим к загрузке");

            isTransitionInProgress = false;
            if (isSearchMode) {
                alert("Фильмы закончились. Попробуйте задать другой запрос.");
                window.location.href = "search.html";
            } else {
                await waitForNewMovies();
            }
            return;
        }

        currentMovie = movieQueue.shift();
        console.log(`--> Вызываем showNextMovieUnified() | Очередь: ${movieQueue.length}, Текущий фильм:`, currentMovie.title_alt);

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
                    console.log("⏳ Очередь пуста после лайка — ставим pendingAutoShow");
                    pendingAutoShow = true;

                    if (!isStreaming) {
                        console.log("🎯 Запускаем ожидание новых фильмов после добавления в избранное");
                        waitForNewMovies();
                    }
                }
            },
            onSkip: async (movie) => {
                void logEvent(userId, "skip", initData);
                if (!isSearchMode) {
                    excludedMovies.push(movie.title_alt);
                    await addToSkipped(userId, movie, initData);
                }
                const skipBtn = document.getElementById('skip-button');
                skipBtn.classList.add('pulse');
                setTimeout(() => skipBtn.classList.remove('pulse'), 200);

                if (movieQueue.length === 0) {
                    console.log("⏳ Очередь пуста после скипа — ставим pendingAutoShow");
                    pendingAutoShow = true;

                    if (!isStreaming) {
                        console.log("🎯 Запускаем ожидание новых фильмов после скипа");
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
                oldCard.addEventListener('transitionend', () => {
                });
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
        console.log("⏳ Ожидаем posterReady + transitionDone...");
        await Promise.all([posterReady, transitionDone]);
        console.log("✅ Постер загружен и transition завершён");
        newCard.classList.add('animate-in');
        newCard.style.opacity = '1';
        preloadNextPoster();

    } catch (e) {
        console.error("Ошибка в transition или posterReady:", e);
    } finally {
        isTransitionInProgress = false;

        if (pendingAutoShow && movieQueue.length > 0 && !isTransitionInProgress) {
            console.log("⏸ Ждём действия пользователя, pendingAutoShow останется true");
        }
    }
}

async function fetchNextBatch() {
    if (movieQueue.length > 0 || isFetching) return;

    console.log("Запрашиваем новую пачку фильмов...");
    showLoader();
    isFetching = true;

    try {
        await fetchStreamingResponse();
    } catch (err) {
        console.error("Ошибка при загрузке фильмов:", err);
        hideLoader();
    } finally {
        isFetching = false;
    }
}

async function waitForNewMovies(retryCount = 0) {
    if (movieQueue.length > 0 && !isTransitionInProgress) {
        console.log("Фильмы найдены, показываем следующий");
        showNextMovieUnified();
        return;
    }

    if (retryCount < 1) {
        console.log("Пробуем снова через 1 секунду (retryCount = %d)", retryCount);
        showLoader();
        setTimeout(async () => {await waitForNewMovies(retryCount + 1);}, 1000);
    } else {
        if (!isStreaming) {
            await fetchNextBatch();
        } else {
            setTimeout(() => waitForNewMovies(retryCount + 1), 1000);
        }
    }
}

document.getElementById('favorite-button').addEventListener('click', async () => {
    vibrateOnClick();
    void logEvent(userId, "like_button", initData);
    favoriteMovies = await addToFavorites(userId, currentMovie, favoriteMovies, initData);
    if (pendingAutoShow) {
        pendingAutoShow = false;
    }
    showNextMovieUnified();
});

document.getElementById('skip-button').addEventListener('click', async() => {
    vibrateOnClick();
    void logEvent(userId, "skip_button", initData);
    if (!isSearchMode) {
        excludedMovies.push(currentMovie.title_alt);
        await addToSkipped(userId, currentMovie, initData);
    }
    if (pendingAutoShow) {
        pendingAutoShow = false;
    }
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
        endOfMatching
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
        endOfMatching
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
        console.warn("🚫 Нет данных для подбора — редиректим на ввод критериев");
        window.location.href = "index.html";
        return;
    }

    initializeFromSession();

    if (!hasSession && hasCriteria) {
        showLoader();
        fetchFavorites(userId, initData).then(result => {
            favoriteMovies = result;
            isTransitionInProgress = false;
            fetchStreamingResponse();
        });
    } else {
        if (currentMovie) {
            console.log("🔄 Восстановлен фильм из сессии:", currentMovie.title_alt);
            showCurrentMovieFromSession(currentMovie);
        } else {
            console.warn("⚠️ currentMovie не найден в сохранённой сессии, показываем следующий");
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

                if (movieQueue.length === 0) {
                    console.log("⏳ Очередь пуста после лайка — ставим pendingAutoShow");
                    pendingAutoShow = true;
                }
            },
            onSkip: async (movie) => {
                void logEvent(userId, "skip", initData);
                if (!isSearchMode) {
                    excludedMovies.push(movie.title_alt);
                    await addToSkipped(userId, movie, initData);
                }
                const skipBtn = document.getElementById('skip-button');
                skipBtn.classList.add('pulse');
                setTimeout(() => skipBtn.classList.remove('pulse'), 200);

                if (movieQueue.length === 0) {
                    console.log("⏳ Очередь пуста после скипа — ставим pendingAutoShow");
                    pendingAutoShow = true;
                }
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

    async function waitForStarsAfterPayment(retryLimit = 20, interval = 1500) {
        for (let i = 0; i < retryLimit; i++) {
            try {
                const response = await apiPost("/user-init", { user_id: userId }, initData);
                if (response.balance && response.balance > 0) {
                    document.getElementById("no-stars-modal").classList.add("hidden");
                    endOfMatching = false;
                    await fetchNextBatch();
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