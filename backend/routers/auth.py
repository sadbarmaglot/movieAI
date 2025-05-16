from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db_managers import UserManager


class PermissionDenied(Exception):
    """Кастомное исключение для логики прав"""
    pass


async def check_user_stars(
    session: AsyncSession,
    user_id: int,
    min_stars: int = 2,
    raise_http: bool = True
) -> bool:
    """
    Проверка, хватает ли звёзд у пользователя. Если raise_http=True — бросает HTTP 403.
    """
    user_manager = UserManager(session=session)
    allowed = await user_manager.check_user_stars_balance(user_id=user_id, min_stars=min_stars)

    if not allowed:
        if raise_http:
            raise HTTPException(status_code=403, detail="Недостаточно звёзд для генерации.")
        raise PermissionDenied("Недостаточно звёзд для генерации.")

    return True