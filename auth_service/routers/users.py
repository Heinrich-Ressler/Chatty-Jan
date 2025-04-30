
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
import models, schemas
from database import get_db
from utils.security import (
    get_password_hash, get_current_user, create_email_token, verify_email_token, send_email,
    verify_password
)

router = APIRouter()


@router.post("/register",
             summary="Регистрация пользователя",
             description="Создает нового пользователя с указанным именем и паролем.",
             tags=["Пользователи"])
async def create_user(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    existing_user = await db.execute(select(models.User).where(models.User.username == user_in.username))
    existing_user = existing_user.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Такой пользователь уже существует")

    user = models.User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/add-mail",
             summary="Запрос на добавление email",
             description="Отправляет ссылку на указанный email для его привязки к аккаунту.",
             tags=["Управление email"])
async def request_add_email(
        email_data: schemas.EmailAdd,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if user.email:
        raise HTTPException(status_code=400, detail="Email уже привязан")

    existing_email = await db.execute(select(models.User).where(models.User.email == email_data.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот email уже используется")

    token = create_email_token({"sub": user.username, "email": email_data.email, "action": "add_email"})
    confirmation_url = f"http://localhost/auth/users/confirm-email?token={token}"
    send_email(
        email_data.email,
        "Подтверждение добавления email",
        f"Перейдите по ссылке для добавления email: {confirmation_url}"
    )
    return {"message": "Ссылка для подтверждения отправлена на ваш email"}


@router.get("/confirm-email", include_in_schema=False)
async def confirm_email(token: str, db: AsyncSession = Depends(get_db)):
    payload = verify_email_token(token)
    if payload.get("action") != "add_email":
        raise HTTPException(status_code=400, detail="Неверный токен")

    username = payload.get("sub")
    email = payload.get("email")
    if not username or not email:
        raise HTTPException(status_code=400, detail="Токен не содержит необходимых данных")

    user = await db.execute(select(models.User).where(models.User.username == username))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.email:
        raise HTTPException(status_code=400, detail="Email уже привязан")

    existing_email = await db.execute(select(models.User).where(models.User.email == email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот email уже используется")

    user.email = email
    user.is_active = True
    await db.commit()
    return {"message": "Email успешно добавлен и подтвержден"}


@router.post("/del-mail",
             summary="Запрос на удаление email",
             description="Отправляет ссылку на текущий email для его отвязки от аккаунта.",
             tags=["Управление email"])
async def request_delete_email(
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if not user.email:
        raise HTTPException(status_code=400, detail="Email не привязан")

    token = create_email_token({"sub": user.username, "action": "delete_email"})
    deletion_url = f"http://localhost/auth/users/delete-email?token={token}"
    send_email(
        user.email,
        "Подтверждение удаления email",
        f"Перейдите по ссылке для удаления email: {deletion_url}"
    )
    return {"message": "Ссылка для удаления email отправлена"}


@router.get("/delete-email", include_in_schema=False)
async def confirm_delete_email(token: str, db: AsyncSession = Depends(get_db)):
    payload = verify_email_token(token)
    if payload.get("action") != "delete_email":
        raise HTTPException(status_code=400, detail="Неверный токен")

    user = await db.execute(select(models.User).where(models.User.username == payload["sub"]))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not user.email:
        raise HTTPException(status_code=400, detail="Email уже удален")

    user.email = None
    user.is_active = False
    await db.commit()
    return {"message": "Email успешно удален"}


@router.post("/del-user",
             summary="Запрос на удаление аккаунта",
             description="Отправляет ссылку на email для удаления аккаунта, если email привязан и активен. Иначе требует пароль.",
             tags=["Пользователи"])
async def delete_user(
        password: schemas.PasswordConfirm | None = None,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if user.email and user.is_active:
        token = create_email_token({"sub": user.username, "action": "delete_user"})
        deletion_url = f"http://localhost/auth/users/delete-user?token={token}"
        send_email(
            user.email,
            "Удаление аккаунта",
            f"Перейдите по ссылке для удаления аккаунта: {deletion_url}"
        )
        return {"message": "Ссылка для удаления аккаунта отправлена"}
    else:
        if not password or not verify_password(password.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Неверный пароль")
        await db.execute(delete(models.User).where(models.User.id == user.id))
        await db.commit()
        return {"message": "Аккаунт удален"}


@router.get("/delete-user", include_in_schema=False)
async def confirm_delete_user(token: str, db: AsyncSession = Depends(get_db)):
    payload = verify_email_token(token)
    if payload.get("action") != "delete_user":
        raise HTTPException(status_code=400, detail="Неверный токен")

    user = await db.execute(select(models.User).where(models.User.username == payload["sub"]))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.execute(delete(models.User).where(models.User.id == user.id))
    await db.commit()
    return {"message": "Аккаунт успешно удален"}


@router.patch("/user-edit",
              summary="Редактирование профиля",
              description="Позволяет изменить имя пользователя, если новое имя не занято.",
              tags=["Пользователи"])
async def edit_user(
        user_data: schemas.UserEdit,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if user_data.username and user_data.username != user.username:
        existing_user = await db.execute(select(models.User).where(models.User.username == user_data.username))
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
        user.username = user_data.username

    await db.commit()
    await db.refresh(user)
    return user
