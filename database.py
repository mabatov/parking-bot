from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/parking_bot")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def check_user_access(user_id: int) -> bool:
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    session.close()
    return user is not None

def add_user(user_id: int) -> bool:
    session = SessionLocal()
    if not check_user_access(user_id):
        new_user = User(telegram_id=user_id)
        session.add(new_user)
        session.commit()
        session.close()
        return True
    session.close()
    return False

def remove_user(user_id: int) -> bool:
    session = SessionLocal()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    if user:
        session.delete(user)
        session.commit()
        session.close()
        return True
    session.close()
    return False

def get_all_users():
    session = SessionLocal()
    users = session.query(User).all()
    session.close()
    return users
