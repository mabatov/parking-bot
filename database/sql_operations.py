from config import config
from database.models import User


class SqlOperations:
    def __init__(self, session_maker):
        self.session_maker = session_maker

    def check_user_access(self, user_id: int) -> bool:
        # Пропускаем проверку для администратора
        if user_id == config.admin_telegram_id:
            return True
        with self.session_maker() as session:
            user = session.query(User).filter(User.telegram_id == user_id).first()
            return user is not None

    def add_user(self, user_id: int) -> bool:
        if not self.check_user_access(user_id):
            new_user = User(telegram_id=user_id)
            with self.session_maker() as session:
                session.add(new_user)
                session.commit()
                return True
        return False

    def remove_user(self, user_id: int) -> bool:
        with self.session_maker() as session:
            user = session.query(User).filter(User.telegram_id == user_id).first()
            if user:
                self.session_maker.delete(user)
                self.session_maker.commit()
                return True
            return False

    def get_all_users(self):
        with self.session_maker() as session:
            users = session.query(User).all()
            return users
