from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime


class UserInitRequest(BaseModel):
    user_id: int


class UserInitResponse(BaseModel):
    user_id: int
    balance: int


class ReferralRequestModel(BaseModel):
    user_id: int
    referred_by: int


class PaymentRequest(BaseModel):
    user_id: int
    amount: Optional[int] = 1


class LogEventRequest(BaseModel):
    user_id: int
    page: str
    action: str
    session_id: str
    timestamp: datetime
    init_data: Optional[str] = ""
    start_param: Optional[str] = ""
    extra: Optional[Dict] = {}


class IOSUserInitRequest(BaseModel):
    device_id: str  # UUID устройства


class IOSUserInitResponse(BaseModel):
    device_id: str


class FeedbackRequest(BaseModel):
    message: str
    contact: Optional[str] = None  # Контакт для обратной связи (email, username, telegram и т.д.)
