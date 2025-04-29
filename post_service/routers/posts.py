# Импортируем FastAPI для создания маршрутов и обработки HTTP-запросов
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
# APIRouter: группирует маршруты
# Depends: инъекция зависимостей
# HTTPException: для HTTP-ошибок
# UploadFile, File: для загрузки файлов

# Импортируем SQLAlchemy для асинхронной работы с базой данных
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
# AsyncSession: асинхронная сессия базы
# select, delete: для SQL-запросов
# func: для подсчёта (лайки, комментарии)

# Импортируем локальные модели и схемы
import models, schemas
# models: ORM-модели Post, Comment, Like
# schemas: Pydantic-схемы для валидации и сериализации

# Импортируем зависимость для получения сессии базы данных
from database import get_db
# get_db: возвращает AsyncSession

# Импортируем утилиты для аутентификации, событий и MinIO
from utils.auth import get_current_user
from utils.events import (
    send_post_created, send_post_deleted,
    send_comment_created, send_comment_deleted,
    send_like_added, send_like_removed
)
from utils.minio import upload_image
# get_current_user: проверяет токен через auth_service
# send_*: отправляют события через FastStream
# upload_image: загружает файлы в MinIO

# Импортируем модули для логирования и генерации имён файлов
import logging
from uuid import uuid4
import mimetypes
# logging: для логов
# uuid4: для уникальных имён файлов
# mimetypes: для проверки типа файла

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Уровень INFO для логов
# logger: объект для записи операций и ошибок

# Создаём роутер для маршрутов постов
router = APIRouter()
# router: объединяет маршруты постов, комментариев, лайков

# ----- Посты -----

@router.post("/", response_model=schemas.PostOut,
             summary="Создать пост",
             description="Создаёт новый пост от имени авторизованного пользователя.",
             tags=["Posts"])
async def create_post(
        post: schemas.PostCreate,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Создание поста
    # post: данные поста (title, content)
    # user: данные пользователя из auth_service
    # db: сессия базы данных

    # Создаём пост
    db_post = models.Post(
        title=post.title,
        content=post.content,
        author_id=user["id"]
    )
    # author_id: берём из токена

    # Добавляем в сессию
    db.add(db_post)
    # Помечаем для вставки

    # Сохраняем
    await db.commit()
    # Выполняем INSERT

    # Обновляем объект
    await db.refresh(db_post)
    # Получаем id, created_at

    # Отправляем событие через FastStream
    await send_post_created(db_post.id, user["id"], db_post.title)
    # Уведомляем о создании поста

    # Запрашиваем данные поста с лайками и комментариями
    result = await db.execute(
        select(models.Post,
               func.count(models.Like.id).label("likes_count"),
               func.count(models.Comment.id).label("comments_count"))
        .outerjoin(models.Like, models.Like.post_id == models.Post.id)
        .outerjoin(models.Comment, models.Comment.post_id == models.Post.id)
        .where(models.Post.id == db_post.id)
        .group_by(models.Post)
    )
    # outerjoin: учитываем отсутствие лайков/комментариев
    # group_by: группируем по посту

    post_out = result.first()
    # Извлекаем результат

    # Логируем создание
    logger.info(f"Post {db_post.id} created by user {user['id']}")

    # Возвращаем пост
    return {
        **post_out[0].__dict__,
        "author_username": user["username"],
        "likes_count": post_out[1],
        "comments_count": post_out[2]
    }
    # Добавляем username автора

@router.get("/", response_model=list[schemas.PostOut],
            summary="Получить все посты",
            description="Возвращает список всех постов с количеством лайков и комментариев.",
            tags=["Posts"])
async def read_all_posts(db: AsyncSession = Depends(get_db)):
    # Получение всех постов
    # db: сессия базы данных

    # Запрашиваем посты
    result = await db.execute(
        select(models.Post,
               func.count(models.Like.id).label("likes_count"),
               func.count(models.Comment.id).label("comments_count"))
        .outerjoin(models.Like, models.Like.post_id == models.Post.id)
        .outerjoin(models.Comment, models.Comment.post_id == models.Post.id)
        .group_by(models.Post)
        .order_by(models.Post.created_at.desc())
    )
    # Сортируем по дате (новые сверху)

    posts = result.all()
    # Извлекаем все посты

    # Формируем ответ
    return [
        {
            **post[0].__dict__,
            "author_username": (await db.execute(
                select(models.User.username).where(models.User.id == post[0].author_id)
            )).scalar() or "unknown",
            "likes_count": post[1],
            "comments_count": post[2]
        } for post in posts
    ]
    # Запрашиваем username (в реальном проекте лучше кэшировать)

@router.get("/{post_id}", response_model=schemas.PostOut,
            summary="Получить пост",
            description="Возвращает пост по его ID с количеством лайков и комментариев.",
            tags=["Posts"])
async def read_post(post_id: int, db: AsyncSession = Depends(get_db)):
    # Получение поста по ID
    # post_id: ID поста
    # db: сессия базы данных

    # Запрашиваем пост
    result = await db.execute(
        select(models.Post,
               func.count(models.Like.id).label("likes_count"),
               func.count(models.Comment.id).label("comments_count"))
        .outerjoin(models.Like, models.Like.post_id == models.Post.id)
        .outerjoin(models.Comment, models.Comment.post_id == models.Post.id)
        .where(models.Post.id == post_id)
        .group_by(models.Post)
    )

    post = result.first()
    # Извлекаем пост

    # Проверяем существование
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Получаем username автора
    username = (await db.execute(
        select(models.User.username).where(models.User.id == post[0].author_id)
    )).scalar() or "unknown"

    # Возвращаем пост
    return {
        **post[0].__dict__,
        "author_username": username,
        "likes_count": post[1],
        "comments_count": post[2]
    }

@router.patch("/{post_id}", response_model=schemas.PostOut,
              summary="Обновить пост",
              description="Обновляет пост, если пользователь является его автором.",
              tags=["Posts"])
async def update_post(
        post_id: int,
        post: schemas.PostUpdate,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Обновление поста
    # post_id: ID поста
    # post: данные для обновления
    # user: данные пользователя
    # db: сессия базы данных

    # Ищем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    db_post = db_post.scalar_one_or_none()
    # scalar_one_or_none: пост или None

    # Проверяем существование
    if not db_post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Проверяем авторство
    if db_post.author_id != user["id"]:
        raise HTTPException(status_code=403, detail="Нет прав для редактирования")
    # Ошибка 403

    # Обновляем поля
    update_data = post.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_post, key, value)
    # exclude_unset: обновляем только переданные поля

    # Сохраняем
    await db.commit()
    # Выполняем UPDATE

    # Обновляем объект
    await db.refresh(db_post)
    # Получаем актуальные данные

    # Запрашиваем лайки и комментарии
    result = await db.execute(
        select(models.Post,
               func.count(models.Like.id).label("likes_count"),
               func.count(models.Comment.id).label("comments_count"))
        .outerjoin(models.Like, models.Like.post_id == models.Post.id)
        .outerjoin(models.Comment, models.Comment.post_id == models.Post.id)
        .where(models.Post.id == post_id)
        .group_by(models.Post)
    )
    post_out = result.first()

    # Логируем обновление
    logger.info(f"Post {post_id} updated by user {user['id']}")

    # Возвращаем пост
    return {
        **post_out[0].__dict__,
        "author_username": user["username"],
        "likes_count": post_out[1],
        "comments_count": post_out[2]
    }

@router.delete("/{post_id}",
               summary="Удалить пост",
               description="Удаляет пост, если пользователь является его автором.",
               tags=["Posts"])
async def delete_post(
        post_id: int,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Удаление поста
    # post_id: ID поста
    # user: данные пользователя
    # db: сессия базы данных

    # Ищем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    db_post = db_post.scalar_one_or_none()
    # scalar_one_or_none: пост или None

    # Проверяем существование
    if not db_post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Проверяем авторство
    if db_post.author_id != user["id"]:
        raise HTTPException(status_code=403, detail="Нет прав для удаления")
    # Ошибка 403

    # Удаляем пост
    await db.execute(delete(models.Post).where(models.Post.id == post_id))
    # Выполняем DELETE

    # Сохраняем
    await db.commit()
    # Фиксируем удаление

    # Отправляем событие
    await send_post_deleted(post_id, user["id"])
    # Уведомляем об удалении

    # Логируем удаление
    logger.info(f"Post {post_id} deleted by user {user['id']}")

    # Возвращаем сообщение
    return {"message": "Пост удалён"}

@router.post("/{post_id}/upload-image",
             summary="Загрузить изображение к посту",
             description="Загружает изображение в MinIO для поста, если пользователь является автором.",
             tags=["Posts"])
async def upload_image(
        post_id: int,
        file: UploadFile = File(...),
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Загрузка изображения
    # post_id: ID поста
    # file: загружаемый файл
    # user: данные пользователя
    # db: сессия базы данных

    # Ищем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    db_post = db_post.scalar_one_or_none()
    # scalar_one_or_none: пост или None

    # Проверяем существование
    if not db_post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Проверяем авторство
    if db_post.author_id != user["id"]:
        raise HTTPException(status_code=403, detail="Нет прав для загрузки изображения")
    # Ошибка 403

    # Проверяем тип файла
    mime_type, _ = mimetypes.guess_type(file.filename)
    if not mime_type or not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Допустимы только изображения")
    # Проверяем, что это изображение

    # Генерируем имя файла
    file_ext = mimetypes.guess_extension(mime_type) or ".jpg"
    filename = f"{uuid4().hex}{file_ext}"
    # uuid4: уникальное имя

    # Читаем файл
    file_data = await file.read()
    # Асинхронное чтение

    # Загружаем в MinIO
    image_url = await upload_image(file_data, filename)
    # Получаем URL

    # Обновляем пост
    db_post.image_url = image_url
    # Устанавливаем URL

    # Сохраняем
    await db.commit()
    # Выполняем UPDATE

    # Обновляем объект
    await db.refresh(db_post)
    # Получаем актуальные данные

    # Логируем загрузку
    logger.info(f"Image uploaded for post {post_id} by user {user['id']}: {image_url}")

    # Возвращаем результат
    return {"message": "Изображение загружено", "image_url": image_url}

# ----- Комментарии -----

@router.post("/{post_id}/comments", response_model=schemas.CommentOut,
             summary="Создать комментарий",
             description="Добавляет комментарий к посту от имени авторизованного пользователя.",
             tags=["Comments"])
async def create_comment(
        post_id: int,
        comment: schemas.CommentCreate,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Создание комментария
    # post_id: ID поста
    # comment: содержимое комментария
    # user: данные пользователя
    # db: сессия базы данных

    # Проверяем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    if not db_post.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Создаём комментарий
    db_comment = models.Comment(
        content=comment.content,
        post_id=post_id,
        author_id=user["id"]
    )
    # author_id: из токена

    # Добавляем в сессию
    db.add(db_comment)
    # Помечаем для вставки

    # Сохраняем
    await db.commit()
    # Выполняем INSERT

    # Обновляем объект
    await db.refresh(db_comment)
    # Получаем id, created_at

    # Отправляем событие
    await send_comment_created(db_comment.id, post_id, user["id"], db_comment.content)
    # Уведомляем о создании

    # Логируем создание
    logger.info(f"Comment created for post {post_id} by user {user['id']}")

    # Возвращаем комментарий
    return {
        **db_comment.__dict__,
        "author_username": user["username"]
    }

@router.get("/{post_id}/comments", response_model=list[schemas.CommentOut],
            summary="Получить комментарии",
            description="Возвращает все комментарии к посту.",
            tags=["Comments"])
async def get_comments(post_id: int, db: AsyncSession = Depends(get_db)):
    # Получение комментариев
    # post_id: ID поста
    # db: сессия базы данных

    # Проверяем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    if not db_post.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Запрашиваем комментарии
    result = await db.execute(
        select(models.Comment).where(models.Comment.post_id == post_id).order_by(models.Comment.created_at)
    )
    comments = result.scalars().all()
    # Получаем все комментарии

    # Формируем ответ
    return [
        {
            **comment.__dict__,
            "author_username": (await db.execute(
                select(models.User.username).where(models.User.id == comment.author_id)
            )).scalar() or "unknown"
        } for comment in comments
    ]
    # Добавляем username

@router.patch("/comments/{comment_id}", response_model=schemas.CommentOut,
              summary="Обновить комментарий",
              description="Обновляет комментарий, если пользователь является его автором.",
              tags=["Comments"])
async def update_comment(
        comment_id: int,
        comment: schemas.CommentUpdate,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Обновление комментария
    # comment_id: ID комментария
    # comment: новое содержимое
    # user: данные пользователя
    # db: сессия базы данных

    # Ищем комментарий
    db_comment = await db.execute(select(models.Comment).where(models.Comment.id == comment_id))
    db_comment = db_comment.scalar_one_or_none()
    # scalar_one_or_none: комментарий или None

    # Проверяем существование
    if not db_comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    # Ошибка 404

    # Проверяем авторство
    if db_comment.author_id != user["id"]:
        raise HTTPException(status_code=403, detail="Нет прав для редактирования")
    # Ошибка 403

    # Обновляем содержимое
    db_comment.content = comment.content
    # Устанавливаем новое содержимое

    # Сохраняем
    await db.commit()
    # Выполняем UPDATE

    # Обновляем объект
    await db.refresh(db_comment)
    # Получаем актуальные данные

    # Логируем обновление
    logger.info(f"Comment {comment_id} updated by user {user['id']}")

    # Возвращаем комментарий
    return {
        **db_comment.__dict__,
        "author_username": user["username"]
    }

@router.delete("/comments/{comment_id}",
               summary="Удалить комментарий",
               description="Удаляет комментарий, если пользователь является его автором.",
               tags=["Comments"])
async def delete_comment(
        comment_id: int,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Удаление комментария
    # comment_id: ID комментария
    # user: данные пользователя
    # db: сессия базы данных

    # Ищем комментарий
    db_comment = await db.execute(select(models.Comment).where(models.Comment.id == comment_id))
    db_comment = db_comment.scalar_one_or_none()
    # scalar_one_or_none: комментарий или None

    # Проверяем существование
    if not db_comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    # Ошибка 404

    # Проверяем авторство
    if db_comment.author_id != user["id"]:
        raise HTTPException(status_code=403, detail="Нет прав для удаления")
    # Ошибка 403

    # Удаляем комментарий
    await db.execute(delete(models.Comment).where(models.Comment.id == comment_id))
    # Выполняем DELETE

    # Сохраняем
    await db.commit()
    # Фиксируем удаление

    # Отправляем событие
    await send_comment_deleted(comment_id, db_comment.post_id, user["id"])
    # Уведомляем об удалении

    # Логируем удаление
    logger.info(f"Comment {comment_id} deleted by user {user['id']}")

    # Возвращаем сообщение
    return {"message": "Комментарий удалён"}

# ----- Лайки -----

@router.post("/{post_id}/like", response_model=schemas.LikeOut,
             summary="Поставить лайк",
             description="Ставит лайк посту от имени авторизованного пользователя.",
             tags=["Likes"])
async def like_post(
        post_id: int,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Добавление лайка
    # post_id: ID поста
    # user: данные пользователя
    # db: сессия базы данных

    # Проверяем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    if not db_post.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Проверяем, не лайкнуто ли
    existing_like = await db.execute(
        select(models.Like).where(models.Like.post_id == post_id, models.Like.user_id == user["id"])
    )
    if existing_like.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Уже лайкнуто")
    # Ошибка 400

    # Создаём лайк
    db_like = models.Like(
        post_id=post_id,
        user_id=user["id"]
    )

    # Добавляем в сессию
    db.add(db_like)
    # Помечаем для вставки

    # Сохраняем
    await db.commit()
    # Выполняем INSERT

    # Обновляем объект
    await db.refresh(db_like)
    # Получаем id

    # Отправляем событие
    await send_like_added(post_id, user["id"])
    # Уведомляем о лайке

    # Логируем лайк
    logger.info(f"Like added to post {post_id} by user {user['id']}")

    # Возвращаем лайк
    return db_like

@router.delete("/{post_id}/like",
               summary="Убрать лайк",
               description="Убирает лайк с поста, если он был поставлен пользователем.",
               tags=["Likes"])
async def unlike_post(
        post_id: int,
        user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    # Удаление лайка
    # post_id: ID поста
    # user: данные пользователя
    # db: сессия базы данных

    # Проверяем пост
    db_post = await db.execute(select(models.Post).where(models.Post.id == post_id))
    if not db_post.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пост не найден")
    # Ошибка 404

    # Ищем лайк
    db_like = await db.execute(
        select(models.Like).where(models.Like.post_id == post_id, models.Like.user_id == user["id"])
    )
    db_like = db_like.scalar_one_or_none()
    # scalar_one_or_none: лайк или None

    # Проверяем существование
    if not db_like:
        raise HTTPException(status_code=404, detail="Лайк не найден")
    # Ошибка 404

    # Удаляем лайк
    await db.execute(
        delete(models.Like).where(models.Like.post_id == post_id, models.Like.user_id == user["id"])
    )
    # Выполняем DELETE

    # Сохраняем
    await db.commit()
    # Фиксируем удаление

    # Отправляем событие
    await send_like_removed(post_id, user["id"])
    # Уведомляем об удалении

    # Логируем удаление
    logger.info(f"Like removed from post {post_id} by user {user['id']}")

    # Возвращаем сообщение
    return {"message": "Лайк удалён"}

