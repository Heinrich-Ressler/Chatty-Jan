from pydantic import BaseModel, ConfigDict, EmailStr

class TokenData(BaseModel):
    username: str | None = None

class UserCreate(BaseModel):
    username: str
    password: str

class UserRead(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool

    class Config:
        from_attributes = True

class EmailAdd(BaseModel):
    email: EmailStr

class PasswordConfirm(BaseModel):
    password: str

class UserEdit(BaseModel):
    username: str | None = None


