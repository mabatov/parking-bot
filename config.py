from dotenv import load_dotenv, find_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    admin_telegram_id: int
    bot_token: str
    rtsp_url: str

    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_name: str

    load_dotenv(find_dotenv('.env'))


config = Settings()
