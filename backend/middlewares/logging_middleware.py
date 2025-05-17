import time
import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from urllib.parse import parse_qs, unquote

from settings import INIT_DATA_HEADER_NAME

logger = logging.getLogger(__name__)


def _extract_user_id_from_init_data(init_data: str) -> int | None:
    try:
        parsed = parse_qs(init_data)
        user_raw = parsed.get("user", [None])[0]
        if not user_raw:
            return None
        user_json = json.loads(unquote(user_raw))
        return user_json.get("id")
    except Exception as e:
        logger.warning("Failed to parse init_data: %s", e)
        return None


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        init_data = request.headers.get(INIT_DATA_HEADER_NAME)
        if init_data:
            user_id = _extract_user_id_from_init_data(init_data)
        else:
            user_id = None
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(
            "%s %s completed in %.2fms [user_id=%s]",
            request.method,
            request.url.path,
            duration,
            user_id if user_id else "unauthorized"
        )
        return response