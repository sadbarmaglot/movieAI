import pytest
from fastapi import status, HTTPException

@pytest.mark.asyncio
async def test_referral_self_referral(user_manager_mock, test_referrer_user_id):
    with pytest.raises(HTTPException) as exc:
        await user_manager_mock.handle_referral(
            referrer_user_id=test_referrer_user_id,
            referred_user_id=test_referrer_user_id
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "Self-referral is not allowed."
    user_manager_mock._check_user_exists.assert_not_called()
    user_manager_mock.session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_referral_already_registered(user_manager_mock, test_referrer_user_id, test_referred_user_id):
    user_manager_mock._check_user_exists.return_value = True

    with pytest.raises(HTTPException) as exc:
        await user_manager_mock.handle_referral(
            referrer_user_id=test_referrer_user_id,
            referred_user_id=test_referred_user_id
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert exc.value.detail == "User already registered."
    user_manager_mock._check_user_exists.assert_called_once_with(user_id=test_referred_user_id)
    user_manager_mock.session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_referral_already_saved(user_manager_mock, test_referrer_user_id, test_referred_user_id):
    user_manager_mock._check_user_exists.return_value = False
    user_manager_mock._check_referral_exists.return_value = True

    result = await user_manager_mock.handle_referral(
        referrer_user_id=test_referrer_user_id,
        referred_user_id=test_referred_user_id
    )

    assert result == {"status": "ok", "message": "Referral already saved."}
    user_manager_mock._save_referral.assert_not_called()

@pytest.mark.asyncio
async def test_referral_saved_when_not_exists(user_manager_mock, test_referrer_user_id, test_referred_user_id):
    user_manager_mock._check_user_exists.return_value = False
    user_manager_mock._check_referral_exists.return_value = False
    user_manager_mock._should_commit = True

    result = await user_manager_mock.handle_referral(
        referrer_user_id=test_referrer_user_id,
        referred_user_id=test_referred_user_id
    )

    assert result == {"status": "ok"}
    user_manager_mock._save_referral.assert_called_once_with(
        referrer_user_id=test_referrer_user_id,
        referred_user_id=test_referred_user_id,
    )
    user_manager_mock.session.commit.assert_called_once()