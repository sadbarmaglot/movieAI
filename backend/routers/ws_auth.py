import logging

from fastapi import WebSocket, status

from middlewares.auth_middleware import check_telegram_signature
from settings import API_KEY

logger = logging.getLogger(__name__)

# Temporary: allow unauthenticated WebSocket connections
# while iOS update with api_key is rolling out.
# Set to True to enforce auth after iOS release.
WS_AUTH_REQUIRED = False


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """
    Validate WebSocket connection before accept().
    Checks api_key or Telegram init_data from query params.
    Returns False and closes connection if auth fails.
    """
    api_key = websocket.query_params.get("api_key")
    init_data = websocket.query_params.get("init_data")

    if (api_key and api_key == API_KEY) or \
       (init_data and check_telegram_signature(init_data)):
        return True

    # Graceful rollout: allow connections without credentials
    # until all clients are updated
    if not WS_AUTH_REQUIRED:
        logger.info(
            f"WebSocket auth skipped (WS_AUTH_REQUIRED=False): path={websocket.url.path}"
        )
        return True

    logger.warning(
        f"WebSocket auth failed: path={websocket.url.path}, "
        f"api_key={'present' if api_key else 'missing'}, "
        f"init_data={'present' if init_data else 'missing'}"
    )
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return False
