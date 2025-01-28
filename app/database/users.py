from typing import Iterable, Type
from fastapi_pagination.ext.sqlmodel import paginate
from fastapi_pagination import Page
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from app.database.engine import engine
from app.models.user import User


def get_user(user_id: int) -> User | None:
    with Session(engine) as session:
        return session.get(User, user_id)


def get_users_all() -> Page[User]:
    with Session(engine) as session:
        statement = select(User)
        return paginate(session, statement)


def create_user(user: User) -> User:
    with Session(engine) as session:
        # Проверка на наличие пользователя с таким же email
        existing_user = session.query(User).filter_by(email=user.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Добавление нового пользователя
        session.add(user)
        try:
            session.commit()
            session.refresh(user)
            return user
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(status_code=400, detail="Database integrity error: " + str(e))


def update_user(user_id: int, user: User) -> Type[User]:
    with Session(engine) as session:
        # Получаем пользователя из базы данных по ID
        db_user = session.get(User, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Получаем данные для обновления из переданного объекта User
        user_data = user.model_dump(exclude_unset=True)

        # Если в данных для обновления есть email, проверяем его уникальность
        if 'email' in user_data:
            # Ищем пользователя с таким же email, исключая текущего пользователя
            existing_user = session.exec(
                select(User).where(User.email == user_data['email'], User.id != user_id)
            ).first()

            if existing_user:
                raise HTTPException(status_code=400, detail="Email already exists")

        # Обновляем данные пользователя
        for key, value in user_data.items():
            setattr(db_user, key, value)

        # Сохраняем изменения в базе данных
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

        return db_user


def delete_user(user_id: int) -> None:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
