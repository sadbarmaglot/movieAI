from fastapi import APIRouter, Depends

from clients import bq_client
from db_managers import UserManager
from routers.dependencies import get_user_manager
from models import (
    UserInitRequest,
    UserInitResponse,
    LogEventRequest,
    ReferralRequestModel,
    PaymentRequest
)
from models.users import IOSUserInitRequest, IOSUserInitResponse

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


