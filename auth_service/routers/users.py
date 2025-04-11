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


@router.post("/register", response_model=schemas.UserRead)
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


@router.post("/add-mail", response_model=schemas.UserRead)
async def add_email(
        email_data: schemas.EmailAdd,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if user.email:
        raise HTTPException(status_code=400, detail="Email уже привязан")

    existing_email = await db.execute(select(models.User).where(models.User.email == email_data.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот email уже используется")

    user.email = email_data.email
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/veri-mail")
async def verify_email_request(
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if not user.email:
        raise HTTPException(status_code=400, detail="Сначала добавьте email")
    if user.is_active:
        raise HTTPException(status_code=400, detail="Email уже подтвержден")

    token = create_email_token({"sub": user.username, "action": "verify_email"})
    verification_url = f"http://localhost/auth/users/verify-email?token={token}"
    send_email(
        user.email,
        "Подтверждение email",
        f"Перейдите по ссылке для подтверждения: {verification_url}"
    )
    return {"message": "Ссылка для подтверждения отправлена на ваш email"}


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    payload = verify_email_token(token)
    if payload.get("action") != "verify_email":
        raise HTTPException(status_code=400, detail="Неверный токен")

    user = await db.execute(select(models.User).where(models.User.username == payload["sub"]))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_active = True
    await db.commit()
    return {"message": "Email успешно подтвержден"}

# ... (остальные эндпоинты остаются без изменений)