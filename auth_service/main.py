
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from routers.auth import router as auth_router
from routers.users import router as users_router
import models
import schemas
from database import get_db

app = FastAPI(
    title="Chatty",
    version="0.0.1",
    openapi_url="/openapi.json",
    description="Волшебный мир общения, если не хочешь получить щелбан, то зарегистрируйся!!!!!",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path="",
    root_path_in_servers=True
)

app.include_router(auth_router, prefix="/auth", tags=["Авторизация"])
app.include_router(users_router, prefix="/users")

@app.get("/",
         response_model=list[schemas.UserRead],
         summary="Для Теста",
         description="Все пользователи",
         tags=["База данных"])
async def read_root(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users