import logging
from fastapi import FastAPI
from routers import post
from utils.minio import ensure_bucket
from utils.events import setup_events
from database import engine
from models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Post Service",
    version="0.0.1",
    description="Сервис для управления постами, комментариями и лайками",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(post.router, prefix="/posts", tags=["Posts"])

@app.on_event("startup")
async def startup_event():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await ensure_bucket()
        setup_events(app)
        logger.info("Post service started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.get("/")
async def root():
    return {"message": "Post service is running!"}