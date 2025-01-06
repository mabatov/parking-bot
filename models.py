from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = Column(db.Integer, unique=True, nullable=False)

