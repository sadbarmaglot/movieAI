import { attachCardEvents } from "./swiper.js"
export const DEFAULT_POSTER = './assets/images/placeholder.jpg';

export function createMovieCard(movie) {
    const card = document.createElement('div');
    card.className = 'movie-card';

    card.innerHTML = `
        <div class="card-inner">
            <div class="card-front">
                <div class="rating-badge kp" id="rating-badge-kp">
                    <img src="./assets/icons/kinopoisk-icon-circle.webp" class="kinopoisk-logo" alt="kinopoisk logo">
                    <span id="rating-value-kp">--</span>
                </div>
                <div class="rating-badge imdb" id="rating-badge-imdb">
                    <img src="./assets/icons/imdb_icon.webp" class="imdb-logo" alt="imdb logo">
                    <span id="rating-value-imdb">--</span>
                </div>
                <img id="movie-poster" src="${movie.poster_url || DEFAULT_POSTER}" alt="movie poster"/>
                <div class="flip-hint" id="flip-hint">
                    <span>Нажми на постер</span>
                    <img src="./assets/icons/arrow_icon.webp" alt="arrow"/>
                </div>
            </div>
            <div class="card-back">
                <div class="movie-genres" id="movie-genres"></div>
                <div class="movie-description" id="movie-description"></div>
                <a id="kinopoisk-link" class="view-on-kinopoisk" target="_blank">
                    <img src="./assets/icons/kinopoisk-icon-circle.webp" class="kinopoisk-icon" alt="kinopoisk logo"/>
                    КиноПоиск
                </a>
            </div>
        </div>
    `;
    return card;
}

function getRatingClass(rating) {
    return rating < 5 ? 'rating-low' :
           rating < 6 ? 'rating-medium' :
           rating < 7 ? 'rating-good' : 'rating-high';
}

export function updateMovieRatings(card, movie) {
    const kpBadge = card.querySelector('#rating-badge-kp');
    const kpRatingValue = card.querySelector('#rating-value-kp');
    const imdbBadge = card.querySelector('#rating-badge-imdb');
    const imdbRatingValue = card.querySelector('#rating-value-imdb');

    const kp = movie.rating_kp || "--";
    const imdb = movie.rating_imdb || "--";

    const fixed_kp = kp.toFixed?.(1) || kp;
    const fixed_imdb = imdb.toFixed?.(1) || imdb;

    kpRatingValue.textContent = fixed_kp;
    imdbRatingValue.textContent = fixed_imdb;

    kpBadge.classList.add(getRatingClass(fixed_kp));
    imdbBadge.classList.add(getRatingClass(fixed_imdb));
}

export function updateMovieDescription(card, movie) {
    const descriptionElement = card.querySelector('#movie-description');
    if (descriptionElement) {
        descriptionElement.textContent = movie.overview;
    }
}

export function updateMovieGenres(card, movie) {
    const genresContainer = card.querySelector('#movie-genres');
    if (genresContainer) {
        genresContainer.innerHTML = '';
        movie.genres.forEach(g => {
            const span = document.createElement('span');
            span.classList.add('genre-tag');
            span.textContent = g.name;
            genresContainer.appendChild(span);
        });
    }
}

export function updateKinopoiskLink(card, movie) {
    const kinopoiskLink = card.querySelector('#kinopoisk-link');
    if (kinopoiskLink) {
        kinopoiskLink.href = `https://www.kinopoisk.ru/film/${movie.movie_id}`;
    }
}

export function fitTitleFontSize(element, maxFontSize = 22, minFontSize = 10) {
    let fontSize = maxFontSize;
    element.style.fontSize = `${fontSize}px`;
    const maxHeight = element.clientHeight;

    while (fontSize > minFontSize && element.scrollHeight > maxHeight + 1) {
        fontSize -= 1;
        element.style.fontSize = `${fontSize}px`;
    }
}

export function updateGlobalMovieTitles(movie) {
    const titleElement = document.getElementById('movie-title-ru');
    titleElement.textContent = movie.title_ru;
    fitTitleFontSize(titleElement, 22, 10);

    const metaElement = document.getElementById('movie-meta');
    metaElement.textContent = `${movie.title_alt} | ${movie.year}`;
    fitTitleFontSize(metaElement, 14, 12);
}

export function updateMovieInfo(card, movie) {
    updateMovieRatings(card, movie);
    updateMovieDescription(card, movie);
    updateMovieGenres(card, movie);
    updateKinopoiskLink(card, movie);
    updateGlobalMovieTitles(movie);
}

export async function renderMovieCard({
    movie,
    container,
    onLike,
    onSkip,
    onTransitionRequest,
    replaceExisting = true,
    animate = true,
    nextMovieQueue = []
}) {
    const card = createMovieCard(movie);
    card.style.opacity = '0';

    updateMovieInfo(card, movie);
    attachCardEvents(card, movie, { onLike, onSkip, onTransitionRequest });

    if (replaceExisting) {
        const oldCard = container.querySelector('.movie-card');
        if (oldCard) oldCard.remove();
    }

    container.insertBefore(card, container.firstChild);

    container.style.display = 'flex';
    container.setAttribute("style", `background: ${movie.background_color} !important;`);

    const img = card.querySelector('#movie-poster');
    const posterReady = new Promise(resolve => {
        img.onload = resolve;
        img.onerror = () => {
            img.src = DEFAULT_POSTER;
            resolve();
        };
        if (img.complete) resolve();
    });
    img.src = movie.poster_url || DEFAULT_POSTER;

    await posterReady;

    if (animate) card.style.opacity = '1';

    // 🔁 Прелоадим следующий постер
    const nextMovie = nextMovieQueue[0];
    if (nextMovie?.poster_url) {
        const preloadImg = new Image();
        preloadImg.src = nextMovie.poster_url;
    }

    return card;
}