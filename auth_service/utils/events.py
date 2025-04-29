
from fastapi import FastAPI
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from config import settings
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

class UserRegisteredEvent(BaseModel):
    user_id: int
    username: str

def setup_events(fastapi_app: FastAPI):
    fastapi_app.state.broker = broker

async def send_user_registered_event(user_id: int, username: str):
    async with broker:
        await broker.connect()  # Явное подключение брокера
        event = UserRegisteredEvent(user_id=user_id, username=username)
        await broker.publish(event, queue="events", routing_key="UserRegistered")
        logger.info(f"Published UserRegistered event for user_id={user_id}")