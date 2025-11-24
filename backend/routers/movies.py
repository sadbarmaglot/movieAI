import re
import json
import logging

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends, Request,
    HTTPException,
    status
)
from fastapi.websockets import WebSocketState
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Callable, Awaitable, TypedDict, Any, Union


from clients import (
    kp_client,
    openai_client_base_async,
    openai_client,
)
from clients.weaviate_client import MovieWeaviateRecommender
from clients.movie_agent import MovieAgent
from db_managers import MovieManager
from models import (
    MovieResponse,
    MovieStreamingRequest,
    QuestionStreamingRequest,
    AddSkippedRequest
)
from typing import Union
from routers.dependencies import get_session, get_movie_manager
from routers.auth import check_user_stars
from settings import ATMOSPHERE_MAPPING

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/search-movies", response_model=List[MovieResponse])
async def search_movies(
    movie_name: str,
    movie_manager: MovieManager = Depends(get_movie_manager),
):
    response = await kp_client.search(query=movie_name)
    await movie_manager.insert_movies(response)
    return [MovieResponse.from_details(m) for m in response]


@router.post("/questions-streaming")
async def questions_streaming(
    body: QuestionStreamingRequest,
    session: AsyncSession = Depends(get_session),
):
    platform = body.platform or "telegram"
    await check_user_stars(session, user_id=body.user_id, platform=platform)
    return await openai_client.stream_questions()

@router.post("/movies-streaming")
async def movies_streaming(
    body: MovieStreamingRequest,
    session: AsyncSession = Depends(get_session),
):
    platform = body.platform or "telegram"
    await check_user_stars(session, user_id=body.user_id, platform=platform)

    return await openai_client.stream_movies(
        user_id=body.user_id,
        platform=platform,
        chat_answers=body.chat_answers,
        genres=body.categories,
        atmospheres=body.atmospheres,
        description=body.description,
        suggestion=body.suggestion,
        start_year=body.start_year,
        end_year=body.end_year,
        exclude=body.exclude,
        favorites=body.favorites
    )

@router.get("/get-movie", response_model=MovieResponse)
async def get_movie(
        movie_id: int,
        movie_manager: MovieManager = Depends(get_movie_manager)
):
    return await movie_manager.get_by_kp_id(kp_id=movie_id)

@router.get("/preview/{params}", response_class=HTMLResponse)
async def preview_movie(
        request: Request,
        params: str,
        movie_manager: MovieManager = Depends(get_movie_manager)
):
    """
    Пример ожидаемого params: 'movie_123456_ref_789012'
    """
    match = re.match(r"movie_(\d+)(?:_ref_(\d+))?", params)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный формат ссылки.")
    movie_id = int(match.group(1))
    ref_user_id = int(match.group(2)) if match.group(2) else None
    movie_data = await movie_manager.get_by_kp_id(kp_id=movie_id)
    return templates.TemplateResponse("preview.html", {
        "request": request,
        "title": movie_data.title_ru,
        "description": movie_data.overview,
        "poster_url": movie_data.poster_url,
        "movie_id": movie_id,
        "ref_user_id": ref_user_id
    })


@router.post("/add-skipped")
async def add_skipped_movie(
    body: AddSkippedRequest,
    movie_manager: MovieManager = Depends(get_movie_manager)
):
    await movie_manager.add_skipped_movies(
        user_id=body.user_id, 
        kp_id=body.movie_id,
        platform=body.platform
    )


async def _process_agent_results(
    websocket: WebSocket,
    agent: MovieAgent,
    user_input: str,
    add_user_message: bool,
    last_tool_call_id_ref: dict,
    locale: str = "ru"
):
    async for result in agent.run_qa(user_input=user_input, add_user_message=add_user_message, locale=locale):
        if websocket.application_state != WebSocketState.CONNECTED:
            break
        await websocket.send_json(result)

        if result["type"] == "question":
            last_tool_call_id_ref["id"] = result["tool_call_id"]
        elif result["type"] == "search":
            await websocket.send_json({"type": "done"})
            await websocket.close()
            return


@router.websocket("/movie-agent-qa")
async def movie_agent_qa_ws(websocket: WebSocket):
    await websocket.accept()

    # Получить locale из первого сообщения или использовать дефолтный
    locale = "ru"  # По умолчанию русский
    
    agent = MovieAgent(
        openai_client=openai_client_base_async,
        kp_client=kp_client,
        recommender=websocket.app.state.recommender
    )
    last_tool_call_id_ref: dict[str, Optional[str]] = {"id": None}

    try:
        while True:
            data = await websocket.receive_json()
            
            # Обновить locale из данных запроса
            if "locale" in data:
                locale = data["locale"]

            if "query" in data:
                last_tool_call_id_ref["id"] = None
                await _process_agent_results(
                    websocket=websocket,
                    agent=agent,
                    user_input=data["query"],
                    add_user_message=True,
                    last_tool_call_id_ref=last_tool_call_id_ref,
                    locale=locale
                )
            elif "answer" in data:
                if last_tool_call_id_ref["id"]:
                    await agent.answer_tool_call(
                        tool_call_id=last_tool_call_id_ref["id"],
                        answer=data["answer"]
                    )
                    last_tool_call_id_ref["id"] = None
                    user_input = ""
                    add_user_message = False
                else:
                    user_input = data["answer"]
                    add_user_message = True
                await _process_agent_results(
                    websocket=websocket,
                    agent=agent,
                    user_input=user_input,
                    add_user_message=add_user_message,
                    last_tool_call_id_ref=last_tool_call_id_ref,
                    locale=locale
                )
            else:
                await websocket.send_json(
                    {"error": "Invalid payload: expected 'query' or 'answer'"}
                )
    except WebSocketDisconnect:
        print("QA WebSocket disconnected")
    except Exception as e:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_json({"error": str(e)})
            await websocket.send_json({"type": "done"})
            await websocket.close()


class UnknownActionError(Exception):
    def __init__(self, action: str):
        self.action = action
        super().__init__(f"Unknown action: {action}")


class BasePayload(TypedDict, total=False):
    action: str
    user_id: Union[int, str]  # int для Telegram, str (device_id) для iOS
    platform: Optional[str]  # 'telegram' or 'ios'
    locale: Optional[str]  # 'ru' or 'en' - локализация клиента
    query: Optional[str]
    genres: Optional[list[str]]
    atmospheres: Optional[list[str]]
    start_year: Optional[int]
    end_year: Optional[int]
    movie_name: Optional[str]
    source_kp_id: Optional[int]
    rating_kp: Optional[float]
    rating_imdb: Optional[float]


async def handle_movie_agent_streaming(websocket: WebSocket, data: dict, agent: MovieAgent):
    platform = data.get("platform", "telegram")
    locale = data.get("locale", "ru")  # Получаем локализацию из запроса
    
    async for result in agent.run_movie_streaming(
        user_id=data["user_id"],
        platform=platform,
        query=data.get("query"),
        genres=data.get("genres"),
        atmospheres=data.get("atmospheres"),
        start_year=data.get("start_year", 1900),
        end_year=data.get("end_year", 2025),
        locale=locale
    ):
        if websocket.application_state != WebSocketState.CONNECTED:
            break
        await websocket.send_json(result)


async def handle_movie_wv_streaming(websocket: WebSocket, data: dict, recommender: MovieWeaviateRecommender):
    genres = data.get("genres")
    if genres and "любой" in genres:
        genres = None

    atmospheres = data.get("atmospheres")
    if atmospheres and "любой" in atmospheres:
        wv_query = None
    else:
        wv_query = ",".join([ATMOSPHERE_MAPPING[a] for a in atmospheres]) if atmospheres else None

    platform = data.get("platform", "telegram")
    locale = data.get("locale", "ru")
    
    async for movie in recommender.movie_generator(
        user_id=data["user_id"],
        platform=platform,
        query=wv_query,
        movie_name=data.get("movie_name") or None,
        genres=genres,
        start_year=data.get("start_year", 1900),
        end_year=data.get("end_year", 2025),
        rating_kp=data.get("rating_kp", 5.0),
        rating_imdb=data.get("rating_imdb", 5.0),
        locale=locale,
    ):
        await websocket.send_text(json.dumps(movie, ensure_ascii=False))

    await websocket.send_text("__END__")


async def handle_similar_movie_streaming(websocket: WebSocket, data: dict, recommender: MovieWeaviateRecommender):
    platform = data.get("platform", "telegram")
    locale = data.get("locale", "ru")  # Получаем локализацию из запроса
    
    async for movie in recommender.movie_generator(
        user_id=data["user_id"],
        platform=platform,
        source_kp_id=data.get("source_kp_id"),
        locale=locale,
    ):
        await websocket.send_text(json.dumps(movie, ensure_ascii=False))

    await websocket.send_text("__END__")


ActionHandler = Callable[[WebSocket, dict, Any], Awaitable[None]]
ACTION_HANDLERS: dict[str, ActionHandler] = {
    "movie_agent_streaming": handle_movie_agent_streaming,
    "movie_wv_streaming": handle_movie_wv_streaming,
    "similar_movie_streaming": handle_similar_movie_streaming,
}


async def send_ws_error(websocket: WebSocket, error: Exception):
    logger.warning(f"WebSocket error: {error}")
    if websocket.application_state == WebSocketState.CONNECTED:
        await websocket.send_json({"error": str(error)})
        await websocket.send_text("__ERROR__")


@router.websocket("/movie_streaming-ws")
async def movie_streaming_ws(websocket: WebSocket):
    await websocket.accept()
    agent = MovieAgent(
        openai_client=openai_client_base_async,
        kp_client=kp_client,
        recommender=websocket.app.state.recommender
    )
    recommender: MovieWeaviateRecommender = websocket.app.state.recommender

    try:
        while True:
            data: BasePayload = await websocket.receive_json()
            action = data.get("action")

            handler = ACTION_HANDLERS.get(action)
            if not handler:
                raise UnknownActionError(action)

            if action == "movie_agent_streaming":
                await handler(websocket, data, agent)
            else:
                await handler(websocket, data, recommender)

    except WebSocketDisconnect:
        logger.info("WebSocket отключился")
    except UnknownActionError as e:
        await send_ws_error(websocket, e)
    except Exception as e:
        await send_ws_error(websocket, e)
