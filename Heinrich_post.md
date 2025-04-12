===== post_service/alembic/versions/post_service_active.py =====



===== post_service/alembic/env.py =====

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from config import settings
from models import Base


# Загружаем конфигурацию Alembic
config = context.config
config.set_main_option("sqlalchemy.url", settings.async_database_url)

# Логирование
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные моделей
target_metadata = Base.metadata


def run_migrations_offline():
    """Запускает Alembic в оффлайн-режиме (без подключения к БД)."""
    context.configure(
        url=settings.async_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Настройка контекста Alembic и выполнение миграций."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """Запуск Alembic в асинхронном режиме."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    """Запускает Alembic в онлайн-режиме с подключением к БД."""
    asyncio.run(run_async_migrations())


# Определяем режим работы и запускаем миграции
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()




===== post_service/alembic/script.py.mako =====

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}





===== post_service/routers/posts.py =====

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, crud
from database import SessionLocal
import os
from fastapi import UploadFile, File
from uuid import uuid4

router = APIRouter()

# Зависимость — подключение к БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----- Посты -----

@router.post("/posts/", response_model=schemas.PostOut)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db)):
    return crud.create_post(db, post)

@router.get("/posts/", response_model=list[schemas.PostOut])
def read_all_posts(db: Session = Depends(get_db)):
    return crud.get_all_posts(db)

@router.get("/posts/{post_id}", response_model=schemas.PostOut)
def read_post(post_id: int, db: Session = Depends(get_db)):
    db_post = crud.get_post(db, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return db_post

@router.put("/posts/{post_id}", response_model=schemas.PostOut)
def update_post(post_id: int, post: schemas.PostUpdate, db: Session = Depends(get_db)):
    return crud.update_post(db, post_id, post)

@router.delete("/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    return crud.delete_post(db, post_id)

# ----- Комментарии -----

@router.post("/comments/", response_model=schemas.CommentOut)
def create_comment(comment: schemas.CommentCreate, db: Session = Depends(get_db)):
    return crud.create_comment(db, comment)

@router.get("/posts/{post_id}/comments", response_model=list[schemas.CommentOut])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    return crud.get_comments_by_post(db, post_id)

@router.put("/comments/{comment_id}", response_model=schemas.CommentOut)
def update_comment(comment_id: int, comment: schemas.CommentUpdate, db: Session = Depends(get_db)):
    return crud.update_comment(db, comment_id, comment.content)

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    return crud.delete_comment(db, comment_id)

# ----- Лайки -----

@router.post("/posts/{post_id}/like")
def like(post_id: int, user_id: int, db: Session = Depends(get_db)):
    result = crud.like_post(db, post_id, user_id)
    if not result:
        raise HTTPException(status_code=400, detail="Уже лайкнуто")
    return {"message": "Лайк добавлен"}

@router.delete("/posts/{post_id}/like")
def unlike(post_id: int, user_id: int, db: Session = Depends(get_db)):
    result = crud.unlike_post(db, post_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Лайк не найден")
    return {"message": "Лайк удалён"}



UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@router.post("/posts/{post_id}/upload-image")
def upload_image(post_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Пост не найден")

    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    post.image_url = f"/{UPLOAD_FOLDER}/{filename}"
    db.commit()
    db.refresh(post)

    return {"message": "Изображение загружено", "image_url": post.image_url}


===== post_service/alembic.ini =====


[alembic]
script_location = alembic
prepend_sys_path = .

sqlalchemy.url = postgresql+asyncpg://postgres:postgres@post_db:5432/PostDB


[loggers]
keys = root, sqlalchemy, alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S





===== post_service/app.py =====

import pika
import json

def send_post_created_event(post_id, user_id):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='events')

    event = {"event": "Post Created", "post_id": post_id, "user_id": user_id}
    channel.basic_publish(exchange='', routing_key='events', body=json.dumps(event))

    connection.close()

# Пример использования
send_post_created_event(456, 123)




===== post_service/config.py =====

from pydantic_settings import BaseSettings, SettingsConfigDict

class PostSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env.local', extra='ignore', case_sensitive=False
    )

    db_host: str = 'post_db'
    db_port: int = 5432
    db_name: str = 'PostDB'
    db_user: str = 'postgres'
    db_password: str = 'postgres'

    @property
    def async_database_url(self) -> str:
        return f'postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}'

    @property
    def sync_database_url(self) -> str:  # <-- вот это добавь
        return f'postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}'


settings = PostSettings()





===== post_service/grud.py =====

from sqlalchemy.orm import Session
import models, schemas

# Посты
def create_post(db: Session, post: schemas.PostCreate):
    db_post = models.Post(**post.dict())
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_all_posts(db: Session):
    return db.query(models.Post).all()

def update_post(db: Session, post_id: int, post: schemas.PostUpdate):
    db_post = get_post(db, post_id)
    if db_post:
        for key, value in post.dict().items():
            setattr(db_post, key, value)
        db.commit()
        db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int):
    db_post = get_post(db, post_id)
    if db_post:
        db.delete(db_post)
        db.commit()
    return db_post


# Комментарии
def create_comment(db: Session, comment: schemas.CommentCreate):
    db_comment = models.Comment(**comment.dict())
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def get_comments_by_post(db: Session, post_id: int):
    return db.query(models.Comment).filter(models.Comment.post_id == post_id).all()

def update_comment(db: Session, comment_id: int, content: str):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        comment.content = content
        db.commit()
        db.refresh(comment)
    return comment

def delete_comment(db: Session, comment_id: int):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        db.delete(comment)
        db.commit()
    return comment


# Лайки
def like_post(db: Session, post_id: int, user_id: int):
    existing_like = db.query(models.Like).filter_by(post_id=post_id, user_id=user_id).first()
    if existing_like:
        return None  # Уже лайкал
    like = models.Like(post_id=post_id, user_id=user_id)
    db.add(like)
    db.commit()
    db.refresh(like)
    return like

def unlike_post(db: Session, post_id: int, user_id: int):
    like = db.query(models.Like).filter_by(post_id=post_id, user_id=user_id).first()
    if like:
        db.delete(like)
        db.commit()
    return like





===== post_service/database.py =====

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Подключение к PostgreSQL
DATABASE_URL = "postgresql://postgres:admin@localhost:5432/post_service_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()




===== post_service/docker-entrypoint.sh =====

#!/bin/bash
set -e


wait_for_db() {
  echo "Waiting for database at $DB_HOST:$DB_PORT..."
  while ! nc -z "$DB_HOST" "$DB_PORT"; do
    echo "Database is not ready yet..."
    sleep 1
  done
  echo "Database is ready!"
}


wait_for_rabbitmq() {
  echo "Waiting for RabbitMQ at $RABBITMQ_HOST:$RABBITMQ_PORT..."
  while ! nc -z "$RABBITMQ_HOST" "$RABBITMQ_PORT"; do
    echo "RabbitMQ is not ready yet..."
    sleep 1
  done
  echo "RabbitMQ is ready!"
}

wait_for_db
wait_for_rabbitmq

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting PostService..."
exec uvicorn main:app --host 0.0.0.0 --port 8006 --reload





===== post_service/Dockerfile =====

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
#RUN pip install --no-cache-dir --upgrade pip \
    #&& pip install --no-cache-dir wheel \
    #&& pip install --no-cache-dir -r requirements.txt


RUN chmod +x docker-entrypoint.sh

EXPOSE 8006

ENTRYPOINT ["./docker-entrypoint.sh"]





===== post_service/main.py =====

from fastapi import FastAPI
from database import Base, engine
from routers import posts  # импортируем роуты
from sqlalchemy import create_engine
from config import settings
app = FastAPI()


# используем sync engine только для миграций или create_all
sync_engine = create_engine(settings.sync_database_url)

# подключаем роуты
app.include_router(posts.router)

@app.get("/")
def root():
    return {"message": "Post service работает!"}



===== post_service/models.py =====

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    image_url = Column(String, nullable=True)  # ссылка на изображение

    comments = relationship("Comment", back_populates="post", cascade="all, delete")
    likes = relationship("Like", back_populates="post", cascade="all, delete")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="comments")

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    user_id = Column(Integer)

    post = relationship("Post", back_populates="likes")





===== post_service/requirements.txt =====

alembic
asyncpg
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pydantic
pydantic-settings
python-jose
python-multipart
pika
wheel





===== post_service/schemas.py =====


from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PostBase(BaseModel):
    title: str
    content: str

class PostCreate(PostBase):
    author_id: int

class PostUpdate(PostBase):
    pass

class PostOut(PostBase):
    id: int
    author_id: int
    created_at: datetime
    image_url: Optional[str] = None

    class Config:
        orm_mode = True


class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    post_id: int
    author_id: int

class CommentUpdate(CommentBase):
    pass

class CommentOut(CommentBase):
    id: int
    post_id: int
    author_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class LikeOut(BaseModel):
    id: int
    post_id: int
    user_id: int

    class Config:
        orm_mode = True
