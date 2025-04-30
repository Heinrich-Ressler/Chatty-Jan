
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=True)  # Email может быть null
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)  # По умолчанию False
