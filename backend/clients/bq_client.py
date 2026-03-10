import json
import asyncio
import logging

from google.cloud import bigquery
from datetime import datetime, timezone

from settings import TABLE_ID, SESSION_TABLE_ID


logger = logging.getLogger(__name__)


class BigQueryClient:
    def __init__(self):
        self.client = bigquery.Client()

    def log_page_view(
        self,
        user_id: int,
        page: str,
        action: str,
        session_id: str,
        timestamp: datetime,
        init_data: str = "",
        start_param: str = "",
        extra: dict = None,
    ) -> dict:
        row = {
            "user_id": user_id,
            "page": page,
            "action": action,
            "session_id": session_id,
            "timestamp": timestamp.isoformat(),
            "init_data": init_data,
            "start_param": start_param,
            "extra": json.dumps(extra or {})
        }

        errors = self.client.insert_rows_json(TABLE_ID, [row])
        if errors:
            logger.error("❌ Ошибка при вставке в BigQuery: %s", errors)
            return {"status": "error"}
        else:
            logger.info("✅ Лог записан в BigQuery")
            return {"status": "ok"}


class SessionLogger:
    """Логирование сессий рекомендаций в BigQuery (movie_sessions)."""

    def __init__(self):
        self.client = bigquery.Client()

    def _log(
        self,
        user_id: str,
        session_id: str,
        action: str,
        locale: str = "",
        extra: dict = None,
    ) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "session_id": session_id,
            "action": action,
            "locale": locale,
            "extra": json.dumps(extra or {}, ensure_ascii=False),
        }
        try:
            errors = self.client.insert_rows_json(SESSION_TABLE_ID, [row])
            if errors:
                logger.error("[SessionLogger] BQ insert error: %s", errors)
            else:
                logger.info(
                    "[SessionLogger] %s logged for session=%s user=%s",
                    action, session_id, user_id
                )
        except Exception as e:
            logger.error("[SessionLogger] Failed to log %s: %s", action, e)

    async def log_event(
        self,
        user_id: str,
        session_id: str,
        action: str,
        locale: str = "",
        extra: dict = None,
    ) -> None:
        """Fire-and-forget async wrapper — не блокирует event loop."""
        await asyncio.to_thread(
            self._log, user_id, session_id, action, locale, extra
        )
