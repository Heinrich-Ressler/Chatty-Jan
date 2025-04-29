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
    base_url: str = "http://localhost"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "posts"
    auth_service_url: str = "http://auth_service:8003/auth/verify"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    @property
    def async_database_url(self) -> str:
        return f'postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}'

settings = PostSettings()