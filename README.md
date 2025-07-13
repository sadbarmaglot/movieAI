# 🎬 movieAI

**movieAI** is an AI-powered movie recommendation assistant. It helps users discover movies via natural language descriptions, interactive questioning, or similar movie suggestions. The backend is built with FastAPI and integrates OpenAI, Weaviate, and the Kinopoisk API.

## 🧠 Features

- Recommend movies from a short description (LLM + vector search)
- Ask follow-up questions to refine preferences
- Recommend similar movies
- Real-time movie streaming via WebSocket
- Favorites, referral system, and user data management

## ⚙️ Tech Stack

- **Backend**: FastAPI, WebSocket, StreamingResponse
- **AI**: OpenAI GPT-4, Weaviate hybrid vector search
- **Data**: PostgreSQL, Kinopoisk API, Google Cloud, BigQuery
- **DevOps**: Docker, GitHub Actions

## 🚀 Getting Started

### With Docker

```bash
cd backend
docker-compose up --build
```

## 🖼️ Frontend

The frontend is implemented as a **Telegram WebApp**, offering an interactive movie selection experience.

### Features
- Swipeable movie cards with flip animations
- Chat-based onboarding with movie description or preference questions
- Real-time movie updates via WebSocket
- Favorites and user history stored in localStorage
- Optimized for mobile and desktop Telegram clients

### Technologies
- HTML, CSS, vanilla JS (no framework)
- WebSocket integration for real-time recommendations
- Adaptive UI for Telegram's environment