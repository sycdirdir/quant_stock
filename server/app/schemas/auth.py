from pydantic import BaseModel
from typing import Optional


class WeChatLoginRequest(BaseModel):
    code: str


class WeChatLoginResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    jwt_token: Optional[str] = None
    expires_in: Optional[int] = None
    error: Optional[str] = None


class UserInfo(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
