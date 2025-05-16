import aiohttp

from sqlalchemy import select, update, insert
from fastapi import status, HTTPException

from db_managers.base import BaseManager, users, referrals, payments
from models import UserInitResponse
from settings import BOT_TOKEN

class UserManager(BaseManager):

    async def check_user_stars_balance(
            self,
            user_id: int,
            min_stars: int,
    ) -> bool:
        result = await self.session.execute(
            select(users.c.balance).where(users.c.user_id == user_id) # type: ignore
        )
        balance = result.scalar_one_or_none()
        if balance is None:
            raise HTTPException(status_code=404, detail="User not found")
        return balance >= min_stars

    async def _check_user_exists(self, user_id: int) -> bool:
        result = await self.session.execute(
            select(1).where(users.c.user_id == user_id) # type: ignore
        )
        return result.scalar_one_or_none() is not None

    async def _check_referral_exists(self, user_id: int) -> bool:
        result = await self.session.execute(
            select(1).where(referrals.c.referred_user_id == user_id) # type: ignore
        )
        return result.scalar_one_or_none() is not None

    async def _save_referral(self, referred_user_id: int, referrer_user_id: int) -> None:
        await self.session.execute(
            insert(referrals).values(
                referred_user_id=referred_user_id,
                referrer_user_id=referrer_user_id
            )
        )

    async def ensure_user_exists(self, user_id: int) -> UserInitResponse:
        async with self.transaction():
            result = await self.session.execute(
                select(users.c.balance).where(users.c.user_id == user_id) # type: ignore
            )
            user_row = result.first()
            if user_row:
                return UserInitResponse(user_id=user_id, balance=user_row.balance)

            balance = 10
            await self.session.execute(
                insert(users).values(user_id=user_id, balance=balance)
            )
            return UserInitResponse(user_id=user_id, balance=balance)

    async def update_balance(self, user_id: int, delta: int):
        await self.session.execute(
            update(users)
            .where(users.c.user_id == user_id) # type: ignore
            .values(balance=users.c.balance + delta)
        )

    async def deduct_user_stars(self, user_id: int, amount: int) -> None:
        async with self.transaction():
            await self.update_balance(user_id, -amount)
            result = await self.session.execute(
                select(referrals).where(
                    referrals.c.referred_user_id == user_id, # type: ignore
                    referrals.c.reward_given == False # type: ignore
                )
            )

            referral = result.fetchone()

            if referral:
                referrer_user_id = referral.referrer_user_id
                await self.update_balance(referrer_user_id, 10)
                await self.session.execute(
                    update(referrals)
                    .where(referrals.c.referred_user_id == user_id) # type: ignore
                    .values(reward_given=True)
                )

    async def save_payment(
            self, user_id: int,
            provider_payment_charge_id: str,
            telegram_payment_charge_id: str,
            total_amount: int,
            currency: str = "XTR"

    ) -> bool:
            payment_exists = await self.session.execute(
                select(payments.c.id)
                .where(payments.c.telegram_payment_charge_id == telegram_payment_charge_id) # type: ignore
            )
            if payment_exists.scalar_one_or_none():
                return False

            await self.session.execute(
                insert(payments).values(
                    user_id=user_id,
                    provider_payment_charge_id=provider_payment_charge_id,
                    telegram_payment_charge_id=telegram_payment_charge_id,
                    total_amount=total_amount,
                    currency=currency
                )
            )
            return True

    async def handle_referral(
            self, referrer_user_id: int,
            referred_user_id: int
    ) -> dict:
        if referrer_user_id == referred_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Self-referral is not allowed."
            )

        async with self.transaction():
            already_registered = await self._check_user_exists(user_id=referred_user_id)
            if already_registered:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already registered."
                )

            referral_exists = await self._check_referral_exists(user_id=referred_user_id)
            if referral_exists:
                return {"status": "ok", "message": "Referral already saved."}

            await self._save_referral(referred_user_id=referred_user_id, referrer_user_id=referrer_user_id)

        return {"status": "ok"}

    @staticmethod
    def _generate_invoice_payload(user_id: int, amount: int) -> dict:
        return {
            "chat_id": user_id,
            "title": "Покупка звёзд",
            "description": f"Вы покупаете {amount} ⭐️ для использования в приложении",
            "payload": f"purchase_{amount}_stars",
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": f"{amount} ⭐️", "amount": amount}]
        }

    async def create_invoice(self, user_id:int,amount: int) -> dict:
        invoice_payload = self._generate_invoice_payload(user_id=user_id, amount=amount)
        print(invoice_payload)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink",
                    json=invoice_payload
            ) as response:
                if response.status == 200:
                    json_data = await response.json()
                    print(json_data)
                    return {"ok": True, "invoice_url": json_data["result"]}

                error_text = await response.text()
                return {"ok": False, "error": f"Telegram API error ({response.status}): {error_text}"}