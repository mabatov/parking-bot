from sqlalchemy import select

from config import config
from database.models import User


class AsyncSqlOperations:
    def __init__(self, session_maker):
        self.session_maker = session_maker

    async def check_user_access(self, user_id: int) -> bool:
        # Пропускаем проверку для администратора
        if user_id == config.admin_telegram_id:
            return True
        async with self.session_maker() as session:
            statement = select(User).where(User.telegram_id == user_id)
            user = await session.execute(statement)
            user = user.scalars().first()
            return user is not None

    async def add_user(self, user_id: int) -> bool:
        if not await self.check_user_access(user_id):
            new_user = User(telegram_id=user_id)
            async with self.session_maker() as session:
                session.add(new_user)
                await session.commit()
                return True
        return False

    async def remove_user(self, user_id: int) -> bool:
        async with self.session_maker() as session:
            statement = select(User).where(User.telegram_id == user_id)
            user = await session.execute(statement)
            user = user.scalars().first()
            if user:
                await session.delete(user)
                await session.commit()
                return True
            return False

    async def get_all_users(self):
        async with self.session_maker() as session:
            users =(await session.scalars(select(User))).all()
            users = [{'id':f.id, 'telegram_id':f.telegram_id} for f in users]
            return users
