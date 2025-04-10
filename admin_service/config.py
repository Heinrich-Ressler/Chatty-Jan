from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "admin_db"
    db_port: int = 5432
    db_name: str = "AdminDB"
    db_user: str = "postgres"
    db_password: str = "postgres"

    @property
    def database_url(self):
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

settings = Settings()
print(settings.database_url)
