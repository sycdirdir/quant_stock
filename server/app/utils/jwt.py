from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from app.config import settings


def create_jwt_token(user_id: str, nickname: Optional[str] = None) -> str:
    payload = {
        "user_id": user_id,
        "nickname": nickname or "",
        "exp": datetime.utcnow() + timedelta(seconds=settings.JWT_EXPIRE_SECONDS)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_jwt_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
