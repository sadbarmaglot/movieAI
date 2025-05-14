import { userId, initData, vibrateOnClick} from '../../common/telegram.js';
import { logEvent } from '../../common/api.js';

export function resetCardStyles(movieCard) {
    movieCard.classList.remove('swiping', 'fly-left', 'fly-right', 'flipped');
    movieCard.style.transition = '';
    movieCard.style.transform = '';
    movieCard.style.opacity = 1;
}

export function attachCardEvents(movieCard, currentMovie, {
    onLike,
    onSkip,
    onTransitionRequest
}) {
    const movieDescription = movieCard.querySelector('#movie-description');

    let swipeStartX = 0;
    let swipeStartY = 0;
    let isSwiping = false;
    let didSwipe = false;
    const swipeThreshold = 100;

    movieCard.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        swipeStartX = touch.clientX;
        swipeStartY = touch.clientY;
        didSwipe = false;
        isSwiping = true;
        movieCard.classList.add('swiping');
        movieCard.style.transition = 'none';
    });

    movieCard.addEventListener('touchmove', (e) => {
        if (!isSwiping) return;
        const touch = e.touches[0];
        const deltaX = touch.clientX - swipeStartX;
        const deltaY = touch.clientY - swipeStartY;

        if (Math.abs(deltaX) > Math.abs(deltaY)) {
            didSwipe = true;
            e.preventDefault();
            movieCard.style.transform = `translateX(${deltaX}px) rotate(${deltaX * 0.05}deg)`;
            movieCard.style.opacity = 1 - Math.min(Math.abs(deltaX) / 300, 0.6);
        }
    });

    movieCard.addEventListener('touchend', async (e) => {
        if (!isSwiping) return;
        isSwiping = false;

        const deltaX = e.changedTouches[0].clientX - swipeStartX;
        movieCard.classList.remove('swiping');
        movieCard.style.transition = '';

        if (Math.abs(deltaX) > swipeThreshold) {
            const direction = deltaX > 0 ? 'fly-right' : 'fly-left';

            movieCard.classList.remove('flipped');

            await new Promise(requestAnimationFrame);
            requestAnimationFrame(() => movieCard.classList.add(direction));

            await new Promise(resolve => {
                const fallback = setTimeout(resolve, 200);
                movieCard.addEventListener('transitionend', () => {
                    clearTimeout(fallback);
                    resolve();
                }, { once: true });
            });

            vibrateOnClick();

            if (direction === 'fly-right') {
                await onLike(currentMovie);
            } else {
                await onSkip(currentMovie);
            }

            onTransitionRequest();
        } else {
            resetCardStyles(movieCard);
        }
    });

    const cardFront = movieCard.querySelector('.card-front');
    const cardBack = movieCard.querySelector('.card-back');

    [cardFront, cardBack].forEach(el => {
        el.addEventListener('click', async () => {
            vibrateOnClick();
            movieCard.classList.remove('swiping');
            isSwiping = false;
            didSwipe = false;
            movieCard.classList.toggle('flipped');
            const hint = movieCard.querySelector('#flip-hint');
            if (hint) hint.style.display = 'none';

            void logEvent(userId, 'flip_poster_card_click', initData);
        });
    });

    ['touchstart', 'touchmove', 'touchend'].forEach(eventType => {
        movieDescription?.addEventListener(eventType, (e) => e.stopPropagation());
    });
}