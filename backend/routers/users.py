from fastapi import APIRouter, Depends, HTTPException, status
import aiohttp
import logging

from clients import bq_client
from db_managers import UserManager
from routers.dependencies import get_user_manager
from models import (
    UserInitRequest,
    UserInitResponse,
    LogEventRequest,
    ReferralRequestModel,
    PaymentRequest,
    FeedbackRequest
)
from models.users import IOSUserInitRequest, IOSUserInitResponse
from settings import BOT_FEEDBACK_TOKEN, ADMIN_ID

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/user-init", response_model=UserInitResponse)
async def init_user(
    body: UserInitRequest,
    user_manager: UserManager = Depends(get_user_manager)
):
    return await user_manager.ensure_user_exists(user_id=body.user_id)

@router.post("/referral")
async def referral(
    body: ReferralRequestModel,
    user_manager: UserManager = Depends(get_user_manager)
):
    return await user_manager.handle_referral(
        referrer_user_id=body.referred_by,
        referred_user_id=body.user_id
    )

@router.post("/create_invoice")
async def create_invoice(
        request: PaymentRequest,
        user_manager: UserManager = Depends(get_user_manager)
):
    return await user_manager.create_invoice(user_id=request.user_id, amount=request.amount)

@router.post("/log-event")
async def log_event(
    body: LogEventRequest,
):
    return bq_client.log_page_view(
        user_id=body.user_id,
        page=body.page,
        action=body.action,
        session_id=body.session_id,
        timestamp=body.timestamp,
        init_data=body.init_data,
        start_param=body.start_param,
        extra=body.extra
    )


@router.post("/ios/user-init", response_model=IOSUserInitResponse)
async def init_ios_user(
    body: IOSUserInitRequest,
    user_manager: UserManager = Depends(get_user_manager)
):
    """Инициализация iOS пользователя по device_id"""
    result = await user_manager.ensure_ios_user_exists(device_id=body.device_id)
    return IOSUserInitResponse(device_id=result["device_id"])


@router.post("/feedback")
async def send_feedback(body: FeedbackRequest):
    """
    Отправляет обратную связь от пользователя в Telegram бот администратору.
    
    Args:
        body: FeedbackRequest с сообщением и контактом для обратной связи
    
    Returns:
        dict: Результат отправки сообщения
    """
    try:
        # Формируем текст сообщения
        feedback_text = "🗣 Обратная связь от пользователя:\n\n"
        feedback_text += f"{body.message}\n\n"
        
        if body.contact:
            feedback_text += f"📧 Контакт для связи: {body.contact}"
        
        # Отправляем сообщение в Telegram
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{BOT_FEEDBACK_TOKEN}/sendMessage"
            payload = {
                "chat_id": ADMIN_ID,
                "text": feedback_text,
                "parse_mode": "Markdown"
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        logger.info(f"Feedback sent successfully to admin {ADMIN_ID}")
                        return {"success": True, "message": "Обратная связь отправлена успешно"}
                    else:
                        error_description = result.get("description", "Unknown error")
                        logger.error(f"Telegram API error: {error_description}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Ошибка отправки сообщения: {error_description}"
                        )
                else:
                    error_text = await response.text()
                    logger.error(f"HTTP error {response.status}: {error_text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Ошибка при отправке сообщения в Telegram"
                    )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending feedback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при отправке обратной связи"
        )


