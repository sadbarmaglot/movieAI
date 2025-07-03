const API_BASE_URL = "https://auto-gens.com";
const API_BASE_URL_WEBSOCKET = "wss://auto-gens.com";
// const API_BASE_URL = "http://localhost:8080";
// const API_BASE_URL_WEBSOCKET = "ws://localhost:8080";

const apiKey = (
  typeof import.meta !== 'undefined' &&
  import.meta.env &&
  import.meta.env.VITE_API_KEY
) || "secret-key";

// GET-запрос
export async function apiGet(endpoint, params, init_data) {
    const url = new URL(`${API_BASE_URL}${endpoint}`);
    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));

    const headers = new Headers({
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        "X-Telegram-Init-Data": init_data || "init_data"
    });

    const response = await fetch(url, { method: "GET", headers });
    if (!response.ok) {
        throw new Error(`Ошибка: ${response.status}`);
    }
    return response.json();
}

// POST-запрос
export async function apiPost(endpoint, body = {}, init_data) {
    const url = `${API_BASE_URL}${endpoint}`;

    const headers = new Headers({
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        "X-Telegram-Init-Data": init_data || "init_data"
    });

    const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body)
    });
    if (!response.ok) {
        throw new Error(`Ошибка: ${response.status}`);
    }
    return response.json();
}

export async function apiPostStream(endpoint, body = {}, onData, onComplete, onError, init_data) {
    const url = `${API_BASE_URL}${endpoint}`;

    const headers = new Headers({
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        "X-Telegram-Init-Data": init_data || "init_data"
    });

    try {
        const response = await fetch(url, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
            keepalive: true
        });

        if (!response.ok) {
            let detail = `Ошибка ${response.status}`;
            try {
                const errorJson = await response.json();
                detail = errorJson.detail || detail;
            } catch (_) {
                // тело не JSON — оставим как есть
            }

            throw {
                status: response.status,
                detail
            };
        }

        if (!response.body) {
            throw new Error("Ошибка: нет стримингового тела ответа");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        async function readWithTimeout(reader, timeout = 60000) {
            return await Promise.race([
                reader.read(),
                new Promise((_, reject) => setTimeout(() => reject(new Error("⏱️ Timeout while reading stream")), timeout))
            ]);
        }

        while (true) {
            let result;
            try {
                result = await readWithTimeout(reader);
            } catch (e) {
                console.error("💥 Ошибка при чтении потока:", e);
                if (typeof onError === "function") onError(e);
                return;
            }
            const {done, value} = result;
            if (done) break;

            buffer += decoder.decode(value, {stream: true});

            let boundary = buffer.lastIndexOf("\n");
            if (boundary === -1) continue;

            const chunk = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 1);

            const lines = chunk.split("\n");
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;

                try {
                    const parsedJson = JSON.parse(trimmed);
                    onData(parsedJson);
                } catch (error) {
                    console.warn("⚠️ Невозможно распарсить JSON:", trimmed, error);
                }
            }
        }
        onComplete();

    } catch (error) {
        console.error("❌ Ошибка запроса в apiPostStream:", error);
        if (typeof onError === "function") {
            onError(error);
        }
    }
}

export function apiWebSocketStream(endpoint, body = {}, onData, onComplete, onError, initData) {
    const socket = new WebSocket(`${API_BASE_URL_WEBSOCKET}${endpoint}`);

    socket.onopen = () => {
        socket.send(JSON.stringify({
            ...body,
            init_data: initData
        }));
    };

    socket.onmessage = (event) => {
        if (event.data === "__END__") {
            if (typeof onComplete === "function") onComplete();
            socket.close();
            return;
        }

        if (event.data === "__ERROR__") {
            const err = new Error("Ошибка на сервере при стриминге");
            if (typeof onError === "function") onError(err);
            socket.close();
            return;
        }

        try {
            const json = JSON.parse(event.data);
            onData(json);
        } catch (e) {
            console.warn("⚠️ Ошибка парсинга JSON из WS:", event.data);
        }
    };

    socket.onerror = (e) => {
        console.error("🔌 WebSocket ошибка:", e);
        if (typeof onError === "function") onError(e);
    };

    return socket;
}

export async function fetchFavorites(userId, initData) {
    try {
        return await apiGet("/get-favorites", { user_id: userId }, initData);
    } catch (error) {
        console.error("Ошибка при запросе избранных фильмов:", error);
    }
}

export async function addToFavorites(userId, currentMovie, favoriteMovies, initData) {
    if (!favoriteMovies.some(fav => fav.movie_id === currentMovie.movie_id)) {
       try {
            await apiPost(
                "/add-favorites",
                {user_id: userId, movie_id: currentMovie.movie_id},
                initData
            );
            favoriteMovies.push(currentMovie);
            return favoriteMovies
        } catch (error) {
            console.error("Ошибка при добавлении в избранное:", error);
        }
    }
}

export async function addToSkipped(userId, currentMovie, initData) {
   try {
        await apiPost(
            "/add-skipped",
            {user_id: userId, movie_id: currentMovie.movie_id},
            initData
        );
    } catch (error) {
        console.error("Ошибка при добавлении в пропущенные:", error);
    }
}

function getOrCreateSessionId() {
    let sessionId = sessionStorage.getItem("session_id");
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem("session_id", sessionId);
    }
    return sessionId;
}

export async function logEvent(
    userId,
    action,
    initData,
    startParam,
) {
    const sessionId = getOrCreateSessionId();
    const logEventBody = {
        user_id: userId,
        page: window.location.pathname || window.location.href,
        action: action,
        timestamp: new Date().toISOString(),
        init_data: initData,
        session_id: sessionId,
        start_param: startParam,
        extra: {
            platform: navigator.platform,
            lang: navigator.language,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            userAgent: navigator.userAgent,
            vendor: navigator.vendor || null,
            screenWidth: window.screen.width,
            screenHeight: window.screen.height,

        }
    };
    await apiPost("/log-event", logEventBody, initData);
}