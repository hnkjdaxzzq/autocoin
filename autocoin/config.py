from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR / 'autocoin.db'}"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    frontend_dir: str = str(BASE_DIR / "frontend")
    debug: bool = False

    class Config:
        env_prefix = "AUTOCOIN_"


settings = Settings()
