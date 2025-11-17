from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db_managers import UserManager


class PermissionDenied(Exception):
    """Кастомное исключение для логики прав"""
    pass


async def check_user_stars(
    session: AsyncSession,
    user_id,
    platform: str = "telegram",
    min_stars: int = 2,
    raise_http: bool = True
) -> bool:
    """
    Проверка доступа пользователя к функционалу.
    Для Telegram: проверяет баланс звезд
    Для iOS: всегда разрешает (монетизация через подписки, проверяется отдельно)
    
    Args:
        user_id: ID пользователя (int для Telegram) или device_id (str для iOS)
        platform: 'telegram' or 'ios'
    """
    # Для iOS не проверяем баланс (монетизация через подписки)
    if platform == "ios":
        return True
    
    # Для Telegram проверяем баланс звезд
    user_manager = UserManager(session=session)
    allowed = await user_manager.check_user_stars_balance(user_id=user_id, min_stars=min_stars)

    if not allowed:
        if raise_http:
            raise HTTPException(status_code=403, detail="Недостаточно звёзд для генерации.")
        raise PermissionDenied("Недостаточно звёзд для генерации.")

    return True