import pytest

from datetime import datetime
from fastapi import status, HTTPException
from unittest.mock import AsyncMock

from models import UserInitResponse
from routers import users
from clients import bq_client
from unittest.mock import patch

@pytest.mark.asyncio
async def test_init_user(user_manager_mock, async_client, test_app, api_headers, test_user_id, test_balance):
    user_manager_mock.ensure_user_exists = AsyncMock(
        return_value=UserInitResponse(user_id=test_user_id, balance=test_balance)
    )
    test_app.dependency_overrides[users.get_user_manager] = lambda: user_manager_mock

    response = await async_client.post("/user-init", json={"user_id": test_user_id}, headers=api_headers)

    assert response.status_code == 200
    assert response.json() == {"user_id": test_user_id, "balance": test_balance}
    user_manager_mock.ensure_user_exists.assert_called_once_with(user_id=test_user_id)

    test_app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_user_init_missing_user_id(async_client, api_headers):
    response = await async_client.post("/user-init", json={}, headers=api_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_invoice(user_manager_mock, async_client, test_app, api_headers, test_user_id, test_amount):
    user_manager_mock.create_invoice = AsyncMock(
        return_value={"ok": True, "invoice_url": "https://t.me/payment/xyz"}
    )
    test_app.dependency_overrides[users.get_user_manager] = lambda: user_manager_mock

    payload = {"user_id": test_user_id, "amount": test_amount}
    response = await async_client.post("/create_invoice", json=payload, headers=api_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "invoice_url": "https://t.me/payment/xyz"}
    user_manager_mock.create_invoice.assert_called_once_with(user_id=payload["user_id"], amount=payload["amount"])

    test_app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_create_invoice_invalid_amount(async_client, api_headers, test_user_id):
    payload = {"user_id": test_user_id, "amount": "free"}
    response = await async_client.post("/create_invoice", json=payload, headers=api_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_referral(user_manager_mock, async_client, test_app, api_headers, test_user_id):
    user_manager_mock.handle_referral = AsyncMock(return_value={"ok": True})

    test_app.dependency_overrides[users.get_user_manager] = lambda: user_manager_mock

    payload = {"user_id": test_user_id, "referred_by": 22222}

    response = await async_client.post("/referral", json=payload, headers=api_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    user_manager_mock.handle_referral.assert_called_once_with(
        referrer_user_id=payload["referred_by"],
        referred_user_id=payload["user_id"]
    )

    test_app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_referral_self_referral(user_manager_mock, async_client, test_app, api_headers, test_user_id):
    async def raise_self_referral(*args, **kwargs):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Self-referral is not allowed.")

    user_manager_mock.handle_referral = AsyncMock(side_effect=raise_self_referral)

    test_app.dependency_overrides[users.get_user_manager] = lambda: user_manager_mock

    payload = {"user_id": test_user_id, "referred_by": test_user_id}
    response = await async_client.post("/referral", json=payload, headers=api_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Self-referral is not allowed."

    test_app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_referral_user_already_registered(user_manager_mock, async_client, test_app, api_headers, test_user_id):
    async def raise_already_registered(*args, **kwargs):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already registered.")

    user_manager_mock.handle_referral = AsyncMock(side_effect=raise_already_registered)

    test_app.dependency_overrides[users.get_user_manager] = lambda: user_manager_mock

    payload = {"user_id": test_user_id, "referred_by": 22222}
    response = await async_client.post("/referral", json=payload, headers=api_headers)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "User already registered."

    test_app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_log_event(user_manager_mock, async_client, test_app, api_headers, test_log_event_payload):
    with patch.object(bq_client, "log_page_view", return_value={"status": "ok"}) as mock_log:
        response = await async_client.post("/log-event", json=test_log_event_payload, headers=api_headers)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        args, kwargs = mock_log.call_args

        assert kwargs["user_id"] == test_log_event_payload["user_id"]
        assert kwargs["page"] == test_log_event_payload["page"]
        assert kwargs["session_id"] == test_log_event_payload["session_id"]
        assert kwargs["action"] == test_log_event_payload["action"]

        actual_ts = kwargs["timestamp"]
        assert isinstance(actual_ts, datetime)
        expected_ts = datetime.fromisoformat(test_log_event_payload["timestamp"].replace("Z", "+00:00"))
        assert actual_ts == expected_ts

        assert kwargs["init_data"] == test_log_event_payload["init_data"]
        assert kwargs["start_param"] == test_log_event_payload["start_param"]
        assert kwargs["extra"] == test_log_event_payload["extra"]

@pytest.mark.asyncio
async def test_log_event_missing_page(async_client, api_headers, test_log_event_payload):
    payload = test_log_event_payload.copy()
    payload.pop("page")

    response = await async_client.post("/log-event", json=payload, headers=api_headers)
    assert response.status_code == 422
