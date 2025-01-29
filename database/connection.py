import time
import contextlib
from loguru import logger
import psycopg2
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from config import config
from database.models import init_db


def wait_for_db():
    for attempt in range(15):
        with contextlib.suppress(psycopg2.OperationalError):
            with psycopg2.connect(
                dbname=config.db_name,
                user=config.db_user,
                password=config.db_password,
                host=config.db_host,
                port=config.db_port,
            ) as conn:
                logger.info("Database is available.")
                break
        logger.info(f"Waiting for database... Attempt {attempt + 1}/15")
        time.sleep(5)
    else:
        logger.error("Database connection failed after 15 attempts.")
        return

    # Инициализация БД после успешного подключения
    init_db(get_engine())


def get_engine() -> Engine:
    return create_engine(
        f'postgresql+psycopg2://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}',
        pool_size=20, max_overflow=0
    )

def get_session_maker():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

def get_async_session_maker():
    engine = create_async_engine(
        f'postgresql+asyncpg://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}',
        pool_size=20, max_overflow=0)
    return async_sessionmaker(bind=engine,  expire_on_commit=False)

# Глобальные сессии
session_maker = get_session_maker()
async_session_maker = get_async_session_maker()
