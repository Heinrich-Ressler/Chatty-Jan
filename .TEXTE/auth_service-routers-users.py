# Импортируем компоненты FastAPI для создания API
from fastapi import APIRouter, Depends, HTTPException
# APIRouter: для создания группы маршрутов API
# Depends: для указания зависимостей (например, сессия базы данных, текущий пользователь)
# HTTPException: для создания HTTP-ошибок с кодом и сообщением

# Импортируем SQLAlchemy для асинхронной работы с базой данных
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
# AsyncSession: асинхронная сессия для неблокирующих запросов
# select, update, delete: функции для создания SQL-запросов SELECT, UPDATE, DELETE

# Импортируем локальные модули models и schemas
import models, schemas
# models: содержит SQLAlchemy ORM модели (например, User) для таблиц базы данных
# schemas: содержит Pydantic модели (например, UserCreate) для валидации данных

# Импортируем функцию get_db для предоставления сессий базы данных
from database import get_db
# get_db: зависимость, возвращающая AsyncSession для работы с базой

# Импортируем функции безопасности из модуля utils.security
from utils.security import (
    get_password_hash, get_current_user, create_email_token, verify_email_token, send_email,
    verify_password
)
# get_password_hash: хеширует пароль для безопасного хранения
# get_current_user: получает текущего пользователя (например, из JWT-токена)
# create_email_token: создает токен для подтверждения email
# verify_email_token: проверяет токен и возвращает его данные
# send_email: отправляет электронное письмо
# verify_password: проверяет совпадение пароля с хешированным

# Создаем объект APIRouter для группировки маршрутов
router = APIRouter()
# Этот роутер будет содержать все маршруты, связанные с пользователями
# Позже подключается к основному приложению FastAPI

# Определяем POST-маршрут /register для регистрации пользователя
@router.post("/register",
             summary="Регистрация пользователя",
             description="Создает нового пользователя с указанным именем и паролем.",
             tags=["Пользователи"])
# summary, description: метаданные для документации API
# tags=["Пользователи"]: группирует маршрут в категорию "Пользователи"
async def create_user(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    # Асинхронная функция для обработки регистрации
    # user_in: тело запроса, валидируется моделью UserCreate (содержит username, password)
    # db: сессия базы данных, получена через зависимость get_db

    # Проверяем, существует ли пользователь с таким именем
    existing_user = await db.execute(select(models.User).where(models.User.username == user_in.username))
    # select(models.User): создает SQL-запрос SELECT для таблицы User
    # .where(...): фильтрует по username из запроса
    # await db.execute: выполняет запрос асинхронно
    # Результат сохраняется в existing_user

    # Извлекаем одного пользователя или None
    existing_user = existing_user.scalar_one_or_none()
    # scalar_one_or_none(): возвращает запись или None, если пользователь не найден
    # Если найдено несколько записей, возникнет ошибка

    # Если пользователь существует, выбрасываем ошибку
    if existing_user:
        raise HTTPException(status_code=400, detail="Такой пользователь уже существует")
    # HTTPException: возвращает ошибку 400 (Bad Request)
    # Запрос прерывается, клиент получает сообщение об ошибке

    # Создаем объект пользователя для базы данных
    user = models.User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password)
    )
    # models.User: экземпляр модели User
    # username: берется из тела запроса
    # hashed_password: пароль хешируется функцией get_password_hash

    # Добавляем пользователя в сессию базы данных
    db.add(user)
    # Помечает user для вставки в базу при коммите

    # Сохраняем изменения в базе
    await db.commit()
    # Выполняет SQL INSERT для user
    # await: ожидает завершения операции

    # Обновляем объект user данными из базы
    await db.refresh(user)
    # Запрашивает актуальные данные (например, id, созданный базой)

    # Возвращаем созданного пользователя
    return user
    # FastAPI сериализует user в JSON, клиент получает данные

# Определяем POST-маршрут /add-mail для запроса на добавление email
@router.post("/add-mail",
             summary="Запрос на добавление email",
             description="Отправляет ссылку на указанный email для его привязки к аккаунту.",
             tags=["Управление email"])
# summary, description, tags: метаданные для документации
async def request_add_email(
        email_data: schemas.EmailAdd,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Функция для обработки запроса на добавление email
    # email_data: тело запроса с email, валидируется моделью EmailAdd
    # user: текущий пользователь, получен через get_current_user (например, из JWT)
    # db: сессия базы данных через get_db

    # Проверяем, не привязан ли уже email
    if user.email:
        raise HTTPException(status_code=400, detail="Email уже привязан")
    # Если user.email не None, выбрасываем ошибку 400
    # Запрос прерывается

    # Проверяем, не используется ли email другим пользователем
    existing_email = await db.execute(select(models.User).where(models.User.email == email_data.email))
    # Запрашивает пользователя с указанным email
    # await db.execute: выполняет запрос

    # Если email занят, выбрасываем ошибку
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот email уже используется")
    # scalar_one_or_none(): возвращает пользователя или None
    # Если пользователь найден, запрос прерывается

    # Создаем токен для подтверждения email
    token = create_email_token({"sub": user.username, "email": email_data.email, "action": "add_email"})
    # create_email_token: генерирует токен (например, JWT)
    # Данные токена: sub (username), email, action ("add_email")

    # Формируем URL для подтверждения
    confirmation_url = f"http://localhost/auth/users/confirm-email?token={token}"
    # http://localhost: базовый URL (для разработки)
    # Путь /auth/users/confirm-email с параметром token

    # Отправляем письмо с подтверждением
    send_email(
        email_data.email,
        "Подтверждение добавления email",
        f"Перейдите по ссылке для добавления email: {confirmation_url}"
    )
    # send_email: отправляет письмо
    # Параметры: получатель (email_data.email), тема, текст с URL

    # Возвращаем сообщение об успехе
    return {"message": "Ссылка для подтверждения отправлена на ваш email"}
    # JSON-ответ подтверждает отправку письма

# Определяем GET-маршрут /confirm-email для подтверждения email
@router.get("/confirm-email", include_in_schema=False)
# include_in_schema=False: скрывает маршрут из документации (для ссылок в письмах)
async def confirm_email(token: str, db: AsyncSession = Depends(get_db)):
    # Функция для подтверждения email
    # token: параметр запроса из URL (например, ?token=...)
    # db: сессия базы данных

    # Проверяем и декодируем токен
    payload = verify_email_token(token)
    # verify_email_token: извлекает данные (sub, email, action) или выбрасывает ошибку

    # Проверяем, что токен для добавления email
    if payload.get("action") != "add_email":
        raise HTTPException(status_code=400, detail="Неверный токен")
    # Если action не "add_email", выбрасываем ошибку 400

    # Извлекаем имя пользователя и email из токена
    username = payload.get("sub")
    email = payload.get("email")
    # sub: имя пользователя, email: email для добавления

    # Проверяем наличие данных в токене
    if not username or not email:
        raise HTTPException(status_code=400, detail="Токен не содержит необходимых данных")
    # Если username или email отсутствуют, выбрасываем ошибку

    # Ищем пользователя по имени
    user = await db.execute(select(models.User).where(models.User.username == username))
    # Выполняем SELECT для пользователя с username

    # Извлекаем пользователя
    user = user.scalar_one_or_none()
    # Возвращает пользователя или None

    # Если пользователь не найден, выбрасываем ошибку
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Ошибка 404 (Not Found)

    # Проверяем, не привязан ли уже email
    if user.email:
        raise HTTPException(status_code=400, detail="Email уже привязан")
    # Если user.email не None, выбрасываем ошибку

    # Проверяем, не занят ли email другим пользователем
    existing_email = await db.execute(select(models.User).where(models.User.email == email))
    # Запрашиваем пользователя с указанным email

    # Если email занят, выбрасываем ошибку
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Этот email уже используется")
    # Если пользователь найден, запрос прерывается

    # Обновляем email и статус пользователя
    user.email = email
    user.is_active = True
    # Устанавливаем email и активируем учетную запись (is_active=True)

    # Сохраняем изменения
    await db.commit()
    # Выполняем UPDATE для таблицы User

    # Возвращаем сообщение об успехе
    return {"message": "Email успешно добавлен и подтвержден"}
    # Подтверждаем добавление email

# Определяем POST-маршрут /del-mail для запроса на удаление email
@router.post("/del-mail",
             summary="Запрос на удаление email",
             description="Отправляет ссылку на текущий email для его отвязки от аккаунта.",
             tags=["Управление email"])
async def request_delete_email(
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Функция для обработки запроса на удаление email
    # user: текущий пользователь
    # db: сессия базы данных

    # Проверяем наличие email
    if not user.email:
        raise HTTPException(status_code=400, detail="Email не привязан")
    # Если user.email пустой, выбрасываем ошибку

    # Создаем токен для удаления email
    token = create_email_token({"sub": user.username, "action": "delete_email"})
    # Данные: sub (username), action ("delete_email")

    # Формируем URL для удаления
    deletion_url = f"http://localhost/auth/users/delete-email?token={token}"
    # Путь /auth/users/delete-email с параметром token

    # Отправляем письмо для подтверждения
    send_email(
        user.email,
        "Подтверждение удаления email",
        f"Перейдите по ссылке для удаления email: {deletion_url}"
    )
    # Отправляем на user.email с темой и ссылкой

    # Возвращаем сообщение об успехе
    return {"message": "Ссылка для удаления email отправлена"}
    # Подтверждаем отправку письма

# Определяем GET-маршрут /delete-email для подтверждения удаления email
@router.get("/delete-email", include_in_schema=False)
# Скрыт из документации
async def confirm_delete_email(token: str, db: AsyncSession = Depends(get_db)):
    # Функция для подтверждения удаления email
    # token: параметр запроса
    # db: сессия базы данных

    # Декодируем токен
    payload = verify_email_token(token)
    # Извлекаем sub и action

    # Проверяем, что токен для удаления email
    if payload.get("action") != "delete_email":
        raise HTTPException(status_code=400, detail="Неверный токен")
    # Если action неверный, выбрасываем ошибку

    # Ищем пользователя по имени
    user = await db.execute(select(models.User).where(models.User.username == payload["sub"]))
    # Запрашиваем по sub из токена

    # Извлекаем пользователя
    user = user.scalar_one_or_none()
    # Возвращает пользователя или None

    # Если пользователь не найден, выбрасываем ошибку
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Ошибка 404

    # Проверяем наличие email
    if not user.email:
        raise HTTPException(status_code=400, detail="Email уже удален")
    # Если email пустой, выбрасываем ошибку

    # Удаляем email и деактивируем учетную запись
    user.email = None
    user.is_active = False
    # Устанавливаем email в None, is_active в False

    # Сохраняем изменения
    await db.commit()
    # Выполняем UPDATE

    # Возвращаем сообщение об успехе
    return {"message": "Email успешно удален"}
    # Подтверждаем удаление

# Определяем POST-маршрут /del-user для запроса на удаление аккаунта
@router.post("/del-user",
             summary="Запрос на удаление аккаунта",
             description="Отправляет ссылку на email для удаления аккаунта, если email привязан и активен. Иначе требует пароль.",
             tags=["Пользователи"])
async def delete_user(
        password: schemas.PasswordConfirm | None = None,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Функция для обработки удаления аккаунта
    # password: необязательный пароль, валидируется PasswordConfirm
    # user: текущий пользователь
    # db: сессия базы данных

    # Проверяем наличие активного email
    if user.email and user.is_active:
        # Если email есть и активен, используем подтверждение по email

        # Создаем токен для удаления
        token = create_email_token({"sub": user.username, "action": "delete_user"})
        # Данные: sub, action ("delete_user")

        # Формируем URL удаления
        deletion_url = f"http://localhost/auth/users/delete-user?token={token}"
        # Путь /auth/users/delete-user

        # Отправляем письмо
        send_email(
            user.email,
            "Удаление аккаунта",
            f"Перейдите по ссылке для удаления аккаунта: {deletion_url}"
        )
        # Отправляем на user.email

        # Возвращаем сообщение
        return {"message": "Ссылка для удаления аккаунта отправлена"}
        # Подтверждаем отправку
    else:
        # Если email отсутствует или неактивен, требуется пароль

        # Проверяем пароль
        if not password or not verify_password(password.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Неверный пароль")
        # Если пароль отсутствует или неверный, выбрасываем ошибку 401

        # Удаляем пользователя
        await db.execute(delete(models.User).where(models.User.id == user.id))
        # Выполняем DELETE по id пользователя

        # Фиксируем изменения
        await db.commit()
        # Завершаем операцию

        # Возвращаем сообщение
        return {"message": "Аккаунт удален"}
        # Подтверждаем удаление

# Определяем GET-маршрут /delete-user для подтверждения удаления аккаунта
@router.get("/delete-user", include_in_schema=False)
# Скрыт из документации
async def confirm_delete_user(token: str, db: AsyncSession = Depends(get_db)):
    # Функция для подтверждения удаления
    # token: параметр запроса
    # db: сессия базы данных

    # Декодируем токен
    payload = verify_email_token(token)
    # Извлекаем sub и action

    # Проверяем токен
    if payload.get("action") != "delete_user":
        raise HTTPException(status_code=400, detail="Неверный токен")
    # Если action неверный, выбрасываем ошибку

    # Ищем пользователя
    user = await db.execute(select(models.User).where(models.User.username == payload["sub"]))
    # Запрашиваем по sub

    # Извлекаем пользователя
    user = user.scalar_one_or_none()
    # Возвращает пользователя или None

    # Если пользователь не найден, выбрасываем ошибку
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Ошибка 404

    # Удаляем пользователя
    await db.execute(delete(models.User).where(models.User.id == user.id))
    # Выполняем DELETE

    # Фиксируем изменения
    await db.commit()
    # Завершаем операцию

    # Возвращаем сообщение
    return {"message": "Аккаунт успешно удален"}
    # Подтверждаем удаление

# Определяем PATCH-маршрут /user-edit для редактирования профиля
@router.patch("/user-edit",
              summary="Редактирование профиля",
              description="Позволяет изменить имя пользователя, если новое имя не занято.",
              tags=["Пользователи"])
async def edit_user(
        user_data: schemas.UserEdit,
        user: models.User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Функция для редактирования профиля
    # user_data: данные для обновления, валидируются UserEdit
    # user: текущий пользователь
    # db: сессия базы данных

    # Проверяем, указано ли новое имя
    if user_data.username and user_data.username != user.username:
        # Если имя новое и отличается от текущего

        # Проверяем, занято ли имя
        existing_user = await db.execute(select(models.User).where(models.User.username == user_data.username))
        # Запрашиваем пользователя с новым именем

        # Если имя занято, выбрасываем ошибку
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
        # Ошибка 400

        # Обновляем имя
        user.username = user_data.username
        # Устанавливаем новое имя

    # Сохраняем изменения
    await db.commit()
    # Выполняем UPDATE

    # Обновляем объект user
    await db.refresh(user)
    # Получаем актуальные данные

    # Возвращаем обновленного пользователя
    return user
    # Сериализуем в JSON