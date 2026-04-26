from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user_PZW4Kp:password_6n6yfp@10.168.1.112:5432/tushare"
    JWT_SECRET: str = "quant_platform_jwt_secret_2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_SECONDS: int = 604800  # 7天

    # 微信 OAuth
    WECHAT_APPID: Optional[str] = None
    WECHAT_APPSECRET: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
