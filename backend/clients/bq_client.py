import json

from google.cloud import bigquery
from datetime import datetime

from settings import TABLE_ID


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
            print("❌ Ошибка при вставке в BigQuery:", errors)
            return {"status": "error"}
        else:
            print("✅ Лог записан в BigQuery")
            return {"status": "ok"}
