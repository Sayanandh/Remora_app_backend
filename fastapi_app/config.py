import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Remora Caregiver Backend (FastAPI)"
    environment: str = os.getenv("ENVIRONMENT", "development")
    # database_url: str | None = os.getenv("DATABASE_URL")
    database_url: str | None = "mongodb+srv://remorateam25_db_user:AKILjXicexkx6YrF@remora.suxl2tk.mongodb.net/Remora?appName=Remora"
    jwt_secret: str = os.getenv("JWT_SECRET", "dev_secret")
    jwt_algorithm: str = "HS256"
    jwt_exp_days: int = 7
    client_origin: str = os.getenv("CLIENT_ORIGIN", "*")
    port: int = int(os.getenv("PORT", "4000"))


@lru_cache
def get_settings() -> Settings:
    return Settings()




