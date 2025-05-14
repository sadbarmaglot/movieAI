from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI


def custom_openapi(app: FastAPI):
    """
    Кастомизация OpenAPI-схемы с добавлением security схемы.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="MovieAI API",
        version="1.0.0",
        description="API for MovieAI",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }

    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return openapi_schema
