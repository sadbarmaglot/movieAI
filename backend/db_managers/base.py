from contextlib import asynccontextmanager
from sqlalchemy import (
    Column,
    Boolean,
    Integer,
    BigInteger,
    String,
    Text,
    MetaData,
    Table,
    Numeric,
    CheckConstraint,
    DateTime,
    func
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from settings import ASYNC_DATABASE_URL

async_engine = create_async_engine(ASYNC_DATABASE_URL, future=True, echo=True, pool_pre_ping=True)
AsyncSessionFactory = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession) # type: ignore

metadata = MetaData()

movies = Table(
    "movies", metadata,
    Column("id", Integer, primary_key=True),
    Column("tmdb_id", Integer, unique=True, nullable=True),
    Column("kp_id", Integer, unique=True, nullable=False),
    Column("title_alt", String(255), nullable=True),
    Column("title_ru", String(255), nullable=True),
    Column("title_gpt", String(255), nullable=True),
    Column("overview", Text, nullable=True),
    Column("poster_url", Text, nullable=True),
    Column("year", Integer, nullable=True),
    Column("trailer_url", Text, nullable=True),
    Column("google_cloud_url", Text, nullable=True),
    Column("rating_kp", Numeric(4, 3), CheckConstraint('rating_kp >= 0 AND rating_kp <= 10'), nullable=True),
    Column("rating_imdb", Numeric(3, 1), CheckConstraint('rating_imdb >= 0 AND rating_imdb <= 10'), nullable=True),
    Column("movie_length", Integer),
    Column("genres", JSONB, nullable=True),
    Column("countries", JSONB, nullable=True),
    Column("background_color", String(255), nullable=True),
)

favorite_movies = Table(
    "favorite_movies", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=False),
    Column("tmdb_id", Integer, nullable=True),
    Column("iswatched", Boolean, nullable=True, default=False),
    Column("kp_id", Integer, nullable=False),
)

skipped_movies = Table(
    "skipped_movies", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, unique=True, nullable=False),
    Column("tmdb_id", Integer, unique=True, nullable=False),
)

payments = Table(
    "payments", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, nullable=False),
    Column("provider_payment_charge_id", String, unique=True, nullable=False),
    Column("telegram_payment_charge_id", String, unique=True, nullable=False),
    Column("total_amount", Numeric(10, 2), nullable=False),
    Column("currency", String, nullable=False),
    Column("payment_date", DateTime, default=func.now())
)

users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, unique=True, nullable=False),
    Column("balance", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
)

referrals = Table(
    "referrals", metadata,
    Column("id", Integer, primary_key=True),
    Column("referred_user_id", BigInteger, unique=True, nullable=False),
    Column("referrer_user_id", BigInteger, nullable=False),
    Column("reward_given", Boolean, nullable=False, server_default="false"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)


class BaseManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для явной транзакции, если нужно.
        """
        async with self.session.begin():
            yield
