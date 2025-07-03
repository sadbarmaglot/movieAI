import {apiGet, fetchFavorites, addToFavorites, apiPost, logEvent} from "../common/api.js";
import {userId, initData, tgBackButton, backButton, vibrateOnClick, shareButton} from "../common/telegram.js";
import {
    updateGlobalMovieTitles,
    updateMovieRatings,
    updateMovieDescription,
    updateMovieGenres,
    updateKinopoiskLink
} from "./matching_modules/movie_card.js"
import { initBottomNav } from "../common/i18n.js";

const movieID = parseInt(sessionStorage.getItem('movieID'));
let movieData;
let favoriteMovies = [];

async function fetchMovie() {
    try {
        return await apiGet("/get-movie", { movie_id: movieID }, initData);
    } catch (error) {
        console.error("Ошибка при запросе данных фильма:", error);
        return {};
    }
}

function updateFavoriteButton() {
    const isFavorite = favoriteMovies.some(movie => movie.movie_id === movieData.movie_id);
    const button = document.getElementById('favorite-button');
    const icon = document.getElementById('favorite-icon');
    const buttonLabel = document.getElementById('button-label')

    if (isFavorite) {
        button.dataset.favorite = "true";
        icon.src = "./assets/icons/remove_favorites_button.webp";
        icon.alt = "Удалить из избранного";
        buttonLabel.textContent = "Удалить"
    } else {
        button.dataset.favorite = "false";
        icon.src = "./assets/icons/favorite_button.webp";
        icon.alt = "Добавить в избранное";
        buttonLabel.textContent = "Избранное"
    }

}

function showMovie(movie) {
    const movieCard = document.querySelector('.movie-card');
    movieCard.classList.remove('animate-in');
    void movieCard.offsetWidth;
    movieCard.classList.add('animate-in');
    movieCard.classList.remove('flipped');

    const movieContainer = document.getElementById('movie-container');
    if (movieContainer.style.display === 'none') {
        movieContainer.style.display = 'flex';
    }

    document.getElementById('movie-poster').src = movie.poster_url;

    movieContainer.setAttribute("style", `background: ${movie.background_color} !important;`);

    updateGlobalMovieTitles(movie);
    updateMovieRatings(movieCard, movie);
    updateMovieGenres(movieCard, movie);
    updateMovieDescription(movieCard, movie);
    updateKinopoiskLink(movieCard, movie);
}

document.getElementById('favorite-button').addEventListener('click', async () => {
    vibrateOnClick();
    const button = document.getElementById('favorite-button');
    const isCurrentlyFavorite = button.dataset.favorite === "true";

    if (isCurrentlyFavorite) {
        favoriteMovies = favoriteMovies.filter(movie => movie.movie_id !== movieData.movie_id);
        try {
            await apiPost("/delete-favorites",
                {user_id: userId, movie_id: movieData.movie_id},
                initData
            );
        } catch (error) {
            console.error("Ошибка при удалении из избранного:", error);
        }
    } else {
        favoriteMovies = await addToFavorites(userId, movieData, favoriteMovies, initData);
    }

    updateFavoriteButton();
    void logEvent(userId, isCurrentlyFavorite ? "remove_from_favorites" : "add_to_favorites", initData);
});

document.getElementById('share-button').addEventListener('click', async () => {
    void logEvent(userId, "share_button", initData);
    await shareButton(movieID);
});

document.getElementById('suggestion-button').addEventListener('click', async () => {
    vibrateOnClick();
    void logEvent(userId, "suggest_similar", initData);
    sessionStorage.setItem('movieSuggestion', movieData.movie_id);
    sessionStorage.setItem('movieCategories', "[]");
    sessionStorage.setItem('movieAtmospheres', "[]");
    sessionStorage.setItem('movieDescription', "");
    sessionStorage.setItem('movieSearch', "");
    sessionStorage.setItem('yearStart', "");
    sessionStorage.setItem('yearEnd', "");

    window.location.href = 'matching.html';

    setTimeout(() => {
        tgBackButton.hide();
        }, 50
    );
});

async function initializeMoviePage() {
    movieData = await fetchMovie();
    if (movieData && movieData.movie_id) {
        favoriteMovies = await fetchFavorites(userId, initData);
        showMovie(movieData);
        updateFavoriteButton();
    } else {
        console.error("Не удалось получить данные о фильме.");
    }
}

document.addEventListener('DOMContentLoaded', async () => {

    backButton("index.html");
    initBottomNav();
    void logEvent(userId, "open", initData);

    await initializeMoviePage();

    const movieCard = document.querySelector(".movie-card");
    const movieDescription = document.getElementById('movie-description');

    function removeHintAnimation() {
        const hintElement = document.getElementById('flip-hint');
        movieCard.removeEventListener("click", removeHintAnimation);
        if (hintElement) {
            hintElement.style.display = 'none';
        }
    }

    movieCard.addEventListener("click", removeHintAnimation);

    let isScrolling = false;
    let startX = 0;
    let startY = 0;
    let recentTouch = false;

    const toggleFlip = async () => {
        if (!isScrolling) {
            movieCard.classList.toggle('flipped');
            vibrateOnClick();
            void logEvent(userId, "flip_poster", initData);
        }
    };

    movieCard.addEventListener('touchstart', (event) => {
        isScrolling = false;
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

    movieCard.addEventListener('touchend', () => {
        recentTouch = true;
        toggleFlip();
        setTimeout(() => {
            recentTouch = false;
        }, 300);
    });

    ['touchstart', 'touchmove', 'touchend'].forEach(eventType => {
        movieDescription.addEventListener(eventType, (event) => {
            event.stopPropagation();
        });
    });

    movieCard.addEventListener('click', (event) => {
        if (!recentTouch) {
            toggleFlip();
        }
    });
});
