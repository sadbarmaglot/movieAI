import {apiPost, fetchFavorites, logEvent} from "../common/api.js";
import { initBottomNav } from "../common/i18n.js";
import {
    userId,
    initData,
    vibrateOnClick,
    showLoader,
    hideLoader,
    shareButton,
    backButton
} from "../common/telegram.js";

let favoriteMovies = [];
let watchedMovies = [];
let movieToDelete = null;
let movieToDeleteTitle = "";
let activeCategory = null;
let isCategoryView = false;
let isWatchedView = false;
let actionsInitialized = false;

const genreIcons = {
    "ДРАМА": "🎭",
    "КОМЕДИЯ": "😂",
    "ТРИЛЛЕР": "🔪",
    "БОЕВИК": "💥",
    "ФАНТАСТИКА": "🚀",
    "ФЭНТЕЗИ": "🧙‍♂️",
    "УЖАСЫ": "👻",
    "ДЕТЕКТИВ": "🕵️",
    "АНИМАЦИЯ": "🎨",
    "МЕЛОДРАМА": "💖",
    "ДОКУМЕНТАЛЬНЫЙ": "📜",
    "КРИМИНАЛ": "🚔",
    "ПРИКЛЮЧЕНИЯ": "🏕️",
    "ИСТОРИЯ": "🏛️",
    "МЮЗИКЛ": "🎶",
    "СЕМЕЙНЫЙ": "👨‍👩‍👧‍👦",
    "СПОРТ": "⚽",
    "ВЕСТЕРН": "🤠",
    "ВОЕННЫЙ": "🎖️",
};

const deleteConfirmModal = document.getElementById("deleteConfirmModal");
const confirmDeleteBtn = document.getElementById("confirmDelete");
const cancelDeleteBtn = document.getElementById("cancelDelete");

document.getElementById("favoritesTab").addEventListener("click", async () => {
    vibrateOnClick();
    void logEvent(userId, "favorites_tab", initData);

    isWatchedView = false;

    document.getElementById("favoritesTab").classList.add("active");
    document.getElementById("watchedTab").classList.remove("active");

    renderMovies();
});

document.getElementById("watchedTab").addEventListener("click", async () => {
    vibrateOnClick();
    void logEvent(userId, "watched_tab", initData);

    isWatchedView = true;

    document.getElementById("watchedTab").classList.add("active");
    document.getElementById("favoritesTab").classList.remove("active");

    renderMovies();
});

document.getElementById("toggleViewSwitch").addEventListener("change", async(event) => {
    vibrateOnClick();
    void logEvent(userId, `toggle_view_${event.target.checked ? 'category' : 'list'}`, initData);

    isCategoryView = event.target.checked;

    document.getElementById("toggleLabel").textContent = isCategoryView ? "Категории" : "Список";
    renderMovies();
});

const scrollToTopButton = document.getElementById("scrollToTop");
scrollToTopButton.style.display = "none";

document.body.addEventListener("scroll", () => {
    const scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
    if (scrollTop > 200) {
        scrollToTopButton.style.display = "flex";
    } else {
        scrollToTopButton.style.display = "none";
    }
});

scrollToTopButton.addEventListener("click", async() => {
    vibrateOnClick();
    void logEvent(userId, "scroll_to_top", initData);

    document.body.scrollTop = 0; // Safari
    document.documentElement.scrollTop = 0; // Chrome, Firefox, etc.
});

function renderMovies() {
    const movies = isWatchedView ? watchedMovies : favoriteMovies;
    if (isCategoryView) {
        renderMoviesGrouped(movies);
    } else {
        renderMoviesList(movies);
    }
}


function getRatingClass(rating) {
    return rating < 5 ? 'rating-low' :
        rating < 6 ? 'rating-medium' :
            rating < 7 ? 'rating-good' : 'rating-high';
}

function createMovieCard(movie) {
    const movieContainer = document.createElement("div");
    movieContainer.classList.add("movie-container");
    movieContainer.setAttribute("style", `background: ${movie.background_color} !important;`);

    const rating_kp = (movie.rating_kp && movie.rating_kp > 0) ? movie.rating_kp.toFixed(1) : "--";
    const kp_class = rating_kp ? getRatingClass(rating_kp) : "";
    const rating_imdb = (movie.rating_imdb && movie.rating_imdb > 0) ? movie.rating_imdb.toFixed(1) : "--";
    const imdb_class = rating_imdb ? getRatingClass(rating_imdb) : "";
    const kinopoisk_url = `https://www.kinopoisk.ru/film/${movie.movie_id}`

    movieContainer.innerHTML = `
    <div class="movie-card">
        <div class="card-front">
            <!-- Рейтинг КиноПоиска -->
            <div class="rating-badge kp ${kp_class}">
                <img src="./assets/icons/kinopoisk-icon-circle.webp" alt="КиноПоиск" title="Рейтинг КиноПоиска" class="kinopoisk-logo">
                <span id="rating-value-kp">${rating_kp}</span>
            </div>
             <!-- Рейтинг IMDb -->
            <div class="rating-badge imdb ${imdb_class}">
                <img src="./assets/icons/imdb_icon.webp" alt="IMDb" title="Рейтинг IMDb" class="imdb-logo">
                <span id="rating-value-imdb">${rating_imdb}</span>
            </div>
            <!-- Постер -->
            <img src="${movie.poster_url}" loading="lazy" alt="Постер">
            <!-- Подсказка -->
            <div class="flip-hint" id="flip-hint">
                <span>Нажми на постер</span>
                <img src="./assets/icons/arrow_icon.webp" alt="Arrow" />
            </div>
        </div>
        <div class="card-back">
            <div class="movie-genres" id="movie-genres"></div>
            <div class="movie-description" id="movie-description">${movie.overview}</div>
            <a id="kinopoisk-link" class="view-on-kinopoisk" target="_blank" href="${kinopoisk_url}">
                <img src="./assets/icons/kinopoisk-icon-circle.webp" alt="КиноПоиск" class="kinopoisk-icon" />
                КиноПоиск
            </a>
        </div>
    </div>
    <div class="movie-title-ru">${movie.title_ru}</div>
    <div class="movie-meta">${movie.title_alt} | ${movie.year}</div>
       
    <div class="actions">
        <div class="action-row">
            <div class="action-button">
                <button class="suggestion-button" data-movie-id="${movie.movie_id}">
                    <img src="./assets/icons/suggestion_button.webp" alt="Совет">
                </button>
                <span class="button-label">Похожие</span>
            </div>
            ${!isWatchedView ? `
                <div class="action-button">
                    <button class="remove-button" data-movie-id="${movie.movie_id}" data-movie-title="${movie.title_ru}">
                        <img src="./assets/icons/remove_favorites_button.webp" alt="Удалить из избранного">
                    </button>
                    <span class="button-label">Удалить</span>
                </div>
            ` : ""}
            ${!movie.is_watched ? `
            <button class="action-button watched-button" 
            data-movie-id="${movie.movie_id}" 
            data-movie-title="${movie.title_ru}">
                <img src="./assets/icons/watched_button.webp" alt="Фильм просмотрен">
                <span class="button-label">Просмотрено</span>
            </button>
        ` : (isWatchedView ? `
            <button class="action-button notwatched-button" 
            data-movie-id="${movie.movie_id}" 
            data-movie-title="${movie.title_ru}">
                <img src="./assets/icons/notwatched_button.webp" alt="Удалить из просмотренных">
                <span class="button-label">Убрать</span>
            </button>
        ` : "")}
        </div>
        <div class="action-row">
            <div class="action-button">
                <button class="share-button" data-movie-id="${movie.movie_id}">
                    <img src="./assets/icons/share_button.webp" alt="Поделиться">
                </button>
                <span class="button-label">Поделиться</span>
            </div>
        </div>
    </div>
    `;

    const genresContainer = movieContainer.querySelector(".movie-genres");
    if (genresContainer) {
        genresContainer.innerHTML = "";
        movie.genres.forEach(genre => {
            const span = document.createElement("span");
            span.classList.add("genre-tag");
            span.textContent = genre.name;
            genresContainer.appendChild(span);
        });
    }

    const movieCard = movieContainer.querySelector('.movie-card');
    const movieDescription = movieContainer.querySelector('.movie-description');

    let isScrolling = false;
    let isTouchOnDescription = false;
    let startX = 0, startY = 0;

    movieCard.addEventListener('touchstart', (event) => {
        isScrolling = false;
        isTouchOnDescription = event.target.closest('.movie-description') !== null;
        const touch = event.touches[0];
        startX = touch.clientX;
        startY = touch.clientY;
    });

    movieCard.addEventListener('touchmove', (event) => {
        const touch = event.touches[0];
        const deltaX = Math.abs(touch.clientX - startX);
        const deltaY = Math.abs(touch.clientY - startY);
        if (deltaX > 10 || deltaY > 10) {
            isScrolling = true;
        }
    });

    let touchedRecently = false;

    movieCard.addEventListener('touchend', (event) => {
        if (!isScrolling && !isTouchOnDescription) {
            vibrateOnClick();
            movieCard.classList.toggle('flipped');
            removeHintAnimation();

            touchedRecently = true;
            setTimeout(() => touchedRecently = false, 300); // сброс через 300мс
        }
    });

    if (movieDescription) {
        ['touchstart', 'touchmove'].forEach(eventType => {
            movieDescription.addEventListener(eventType, (event) => {
                event.stopPropagation();
            });
        });

        movieDescription.addEventListener('touchend', (event) => {
            event.stopPropagation();
            event.preventDefault();
        });
    }

    movieCard.addEventListener('click', (event) => {
        if (touchedRecently) return; // игнорируем click, если уже был touch
        const isDescription = event.target.closest('.movie-description');
        if (!isDescription) {
            vibrateOnClick();
            movieCard.classList.toggle('flipped');
            removeHintAnimation();
        }
    });

    return movieContainer
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function setupMovieActions() {

    if (actionsInitialized) return;
    actionsInitialized = true;

    const container = document.getElementById('favoriteMovies');

    container.addEventListener('click', async function (event) {
        const watchedBtn = event.target.closest('.watched-button');
        const notWatchedBtn = event.target.closest('.notwatched-button');
        const removeBtn = event.target.closest('.remove-button');
        const shareBtn = event.target.closest('.share-button');
        const suggestionBtn = event.target.closest('.suggestion-button');

        if (watchedBtn) {
            vibrateOnClick();
            void logEvent(userId, "mark_as_watched", initData);
            const movieId = watchedBtn.getAttribute('data-movie-id');
            const movieTitle = watchedBtn.getAttribute('data-movie-title');
            const movieCard = watchedBtn.closest(".movie-container");
            const scrollPosition = window.scrollY;

            if (movieCard) {
                movieCard.classList.add("fade-out");
                await sleep(300);

                try {
                    await apiPost(
                        "/watch-favorites",
                        {
                            user_id: userId,
                            movie_id: movieId,
                            is_watched: true
                        },
                        initData
                    );

                    showWatchedOrNotPopup(movieTitle, true);

                    const allMovies = await fetchFavorites(userId, initData);
                    favoriteMovies = allMovies.filter(m => !m.is_watched).sort((a, b) => b.order_id - a.order_id);
                    watchedMovies = allMovies.filter(m => m.is_watched).sort((a, b) => b.order_id - a.order_id);

                    renderMovies();
                    setTimeout(() => window.scrollTo(0, scrollPosition), 100);

                } catch (error) {
                    console.error("Ошибка при отметке как просмотренного:", error);
                }
            }
        }

        if (notWatchedBtn) {
            vibrateOnClick();
            void logEvent(userId, "unmark_watched", initData);
            const movieId = notWatchedBtn.getAttribute('data-movie-id');
            const movieTitle = notWatchedBtn.getAttribute('data-movie-title');
            const movieCard = notWatchedBtn.closest(".movie-container");
            const scrollPosition = window.scrollY;

            if (movieCard) {
                movieCard.classList.add("fade-out");
                await sleep(300);
                try {
                    await apiPost(
                        "/watch-favorites",
                        {
                            user_id: userId,
                            movie_id: movieId,
                        is_watched: false
                        },
                        initData
                    );

                    showWatchedOrNotPopup(movieTitle, false);

                    const allMovies = await fetchFavorites(userId, initData);
                    favoriteMovies = allMovies.filter(m => !m.is_watched).sort((a, b) => b.order_id - a.order_id);
                    watchedMovies = allMovies.filter(m => m.is_watched).sort((a, b) => b.order_id - a.order_id);

                    renderMovies();
                    setTimeout(() => window.scrollTo(0, scrollPosition), 100);
                } catch (error) {
                        console.error("Ошибка при удалении из просмотренных:", error);
                }
            }
        }

        if (removeBtn) {
            vibrateOnClick();
            void logEvent(userId, "remove_from_favorites", initData);
            movieToDelete = removeBtn.getAttribute('data-movie-id');
            movieToDeleteTitle = removeBtn.getAttribute("data-movie-title");
            deleteConfirmModal.style.display = "flex";
        }

        if (shareBtn) {
            const movieId = shareBtn.getAttribute('data-movie-id');
            void logEvent(userId, "share_button", initData);
            await shareButton(movieId);
        }

        if (suggestionBtn) {
            vibrateOnClick();
            const movieId = suggestionBtn.getAttribute('data-movie-id');
            void logEvent(userId, "find_similar", initData);
            sessionStorage.setItem('movieSuggestion', movieId);
            sessionStorage.setItem('movieCategories', "[]");
            sessionStorage.setItem('movieAtmospheres', "[]");
            sessionStorage.setItem('movieDescription', "");
            sessionStorage.setItem('movieSearch', "");
            sessionStorage.setItem('yearStart', "");
            sessionStorage.setItem('yearEnd', "");

            window.location.href = 'matching.html';
        }
    });
}

function renderMoviesList(movies) {
    const container = document.getElementById("favoriteMovies");
    container.innerHTML = "";
    container.classList.remove("single-column");

    movies.forEach(movie => {
        const movieContainer = createMovieCard(movie);
        container.appendChild(movieContainer);
    });

    setupMovieActions();
}

function renderMoviesGrouped(movies) {
    const container = document.getElementById("favoriteMovies");
    container.innerHTML = "";
    container.classList.add("single-column");

    const categories = {};

    movies.forEach(movie => {
        movie.genres.forEach(genreObj => {
            const genre = genreObj.name.toUpperCase();
            if (!categories[genre]) categories[genre] = [];
            categories[genre].push(movie);
        });
    });

    const sortedCategories = Object.entries(categories).sort((a, b) => b[1].length - a[1].length);

    sortedCategories.forEach(([category, movies]) => {
        const block = document.createElement("div");
        block.classList.add("category-block");

        const icon = genreIcons[category] || "🎬";
        const header = document.createElement("div");
        header.classList.add("category-header");
        header.innerHTML = `<h2>${icon} ${category} (${movies.length})</h2>`;

        const moviesContainer = document.createElement("div");
        moviesContainer.classList.add("movies-container");

        movies.forEach(movie => {
            const movieContainer = createMovieCard(movie);
            moviesContainer.appendChild(movieContainer);
        });

        header.addEventListener("click", () => {
            vibrateOnClick();
            if (moviesContainer.dataset.animating) return;

            if (activeCategory && activeCategory !== moviesContainer) {
                activeCategory.classList.remove("open");
                activeCategory.style.display = "none";
            }

            if (!moviesContainer.classList.contains("open")) {
                moviesContainer.style.display = "flex";
                moviesContainer.dataset.animating = "true";
                setTimeout(() => {
                    delete moviesContainer.dataset.animating;
                    moviesContainer.classList.add("open");
                    activeCategory = moviesContainer;
                    header.scrollIntoView({behavior: "smooth", block: "start"});
                }, 10);
            } else {
                moviesContainer.classList.remove("open");
                moviesContainer.dataset.animating = "true";
                setTimeout(() => {
                    delete moviesContainer.dataset.animating;
                    moviesContainer.style.display = "none";
                    activeCategory = null;
                }, 300);
            }
        });

        block.appendChild(header);
        block.appendChild(moviesContainer);
        container.appendChild(block);
    });

    setupMovieActions();
}

document.addEventListener("touchstart", function () {
    if (window.scrollY === 0) {
        window.scrollTo(0, 1);
    }
});

function removeHintAnimation() {
    document.querySelectorAll('.flip-hint').forEach(hintElement => {
        hintElement.style.display = 'none';
    });
}

function showWatchedOrNotPopup(title, isWatched) {
    const popupMessage = document.getElementById("popupMessage");
    let text
    if (isWatched) {
        text = `"${title}" перемещен в просмотренные`;
    } else {
        text = `"${title}" удален из просмотренных`;
    }
    popupMessage.textContent = text;
    popupMessage.style.display = "block";
    setTimeout(() => {
        popupMessage.style.display = "none";
    }, 3000);
}

document.addEventListener("click", async (event) => {
    if (event.target.closest(".share-button")) {
        const button = event.target.closest(".share-button");
        const movieID = button.getAttribute("data-movie-id");
        await shareButton(movieID);
    }
});

confirmDeleteBtn.addEventListener("click", async () => {
    vibrateOnClick();
    void logEvent(userId, "confirm_remove_from_favorites", initData);

    const movieCard = document.querySelector(`.remove-button[data-movie-id="${movieToDelete}"]`)?.closest(".movie-container");
    const scrollPosition = window.scrollY;

    if (movieCard) {
        movieCard.classList.add("fade-out");
        await sleep(300);

        try {
            await apiPost("/delete-favorites",
                {user_id: userId, movie_id: movieToDelete},
                initData
            );
        } catch (error) {
            console.error("Ошибка при удалении из избранного:", error);
        } finally {
            deleteConfirmModal.classList.add("fade-out");
            setTimeout(() => {
                deleteConfirmModal.style.display = "none";
                deleteConfirmModal.classList.remove("fade-out");
            }, 300);

            showPopup();

            const allMovies = await fetchFavorites(userId, initData);
            favoriteMovies = allMovies.filter(m => !m.is_watched).sort((a, b) => b.order_id - a.order_id);
            watchedMovies = allMovies.filter(m => m.is_watched).sort((a, b) => b.order_id - a.order_id);

            renderMovies();

            setTimeout(() => {
                window.scrollTo(0, scrollPosition);
            }, 100);
        }
    } else {
        deleteConfirmModal.classList.add("fade-out");
        setTimeout(() => {
            deleteConfirmModal.style.display = "none";
            deleteConfirmModal.classList.remove("fade-out");
        }, 300);

        showPopup();
        favoriteMovies = await fetchFavorites(userId, initData);
        renderMovies();
    }
});

cancelDeleteBtn.addEventListener("click", async() => {
    vibrateOnClick();
    void (userId, "cancel_remove_from_favorites", initData);
    deleteConfirmModal.classList.add("fade-out");
    setTimeout(() => {
        deleteConfirmModal.style.display = "none";
        deleteConfirmModal.classList.remove("fade-out");
    }, 300);
});

function showPopup() {
    const popupMessage = document.getElementById("popupMessage");
    popupMessage.textContent = `"${movieToDeleteTitle}" удален из избранного`;
    popupMessage.style.display = "block";
    setTimeout(() => {
        popupMessage.style.display = "none";
    }, 3000);
}

document.addEventListener('DOMContentLoaded', async () => {

    backButton("index.html");
    initBottomNav();
    void logEvent(userId, "open", initData);

    const toggleSwitch = document.getElementById("toggleViewSwitch");
    const toggleLabel = document.getElementById("toggleLabel");

    toggleSwitch.checked = false;
    toggleLabel.textContent = "Список"

    showLoader();

    const allMovies = await fetchFavorites(userId, initData);
    favoriteMovies = allMovies.filter(m => !m.is_watched).sort((a, b) => b.order_id - a.order_id);
    watchedMovies = allMovies.filter(m => m.is_watched).sort((a, b) => b.order_id - a.order_id);

    renderMovies();
    hideLoader();
});