from sqlalchemy import Column, Integer, Connection, Engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False)

def init_db(connection:Connection|Engine):
    Base.metadata.create_all(bind=connection)