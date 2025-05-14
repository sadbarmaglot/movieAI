from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health", tags=["Health"])
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)
