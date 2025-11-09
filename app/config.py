import json
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # PostgreSQL Database
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    
    # JWT Security
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Cookies
    COOKIE_ACCESS_NAME: str = "access_token"
    COOKIE_REFRESH_NAME: str = "refresh_token"
    
    # Application Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: str
    
    # PgAdmin (опционально)
    PGADMIN_EMAIL: Optional[str] = None
    PGADMIN_PASSWORD: Optional[str] = None
    
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    

    @computed_field
    @property
    def cors_origins_list(self) -> List[Union[str, AnyHttpUrl]]:
        """Парсим JSON строку в список origins"""
        try:
            origins = json.loads(self.CORS_ORIGINS)
            return [str(origin) for origin in origins]
        except json.JSONDecodeError:
            # Если JSON невалидный, возвращаем пустой список
            return []


    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()