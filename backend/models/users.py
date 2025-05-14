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

