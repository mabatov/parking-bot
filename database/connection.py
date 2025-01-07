import time
from loguru import logger
import psycopg2
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from config import config
from database.models import init_db


def wait_for_db():
    count = 0
    while True:
        if count > 15:
            logger.error("Database connection failed.")
            break
        try:
            # Попытка подключиться к базе данных
            conn = psycopg2.connect(
                dbname=config.db_name,
                user=config.db_user,
                password=config.db_password,
                host=config.db_host,
                port=config.db_port,
            )
            init_db(get_engine())
            conn.close()  # Закрываем соединение, так как оно нам не нужно
            break  # Если соединение прошло успешно, выходим из цикла
        except psycopg2.OperationalError:
            count += 1
            logger.info("Waiting for database...")
            time.sleep(5)  # Повторная попытка через 5 секунд


def get_engine() -> Engine:
    engine = create_engine(
        f'postgresql+psycopg2://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}',
        pool_size=20, max_overflow=0)
    return engine


def get_session_maker():
    engine = get_engine()
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session


def get_async_session_maker():
    engine = create_async_engine(
        f'postgresql+asyncpg://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}',
        pool_size=20, max_overflow=0)
    async_session = async_sessionmaker(bind=engine,  expire_on_commit=False)
    return async_session


session_maker = get_session_maker()
get_async_session_maker = get_async_session_maker()
