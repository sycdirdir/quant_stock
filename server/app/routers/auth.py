from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.auth import WeChatLoginRequest, WeChatLoginResponse, UserInfo
from app.utils.jwt import create_jwt_token
from app.utils.auth import get_current_user
from app.database import AsyncSessionLocal
from app.models.user import User
from app.config import settings
from sqlalchemy import select
import logging

router = APIRouter(prefix="/api/auth", tags=["认证"])
logger = logging.getLogger(__name__)


# 开发模式模拟用户
MOCK_USERS = {
    "dev_user_001": {"nickname": "开发用户", "avatar_url": None},
    "dev_user_002": {"nickname": "测试用户", "avatar_url": None},
    "dev_admin": {"nickname": "管理员", "avatar_url": None},
}


class MockLoginRequest(BaseModel):
    user_id: str  # dev_user_001, dev_user_002, dev_admin


@router.get("/wechat/qr")
async def get_wechat_qr():
    """获取微信登录二维码URL（用于前端展示）"""
    # 检查是否配置了微信
    if settings.WECHAT_APPID:
        # 微信已配置，返回真实二维码URL
        return {
            "qr_url": "https://open.weixin.qq.com/connect/qrcode/qrcode_placeholder",
            "scene_str": "quant_login",
            "mode": "wechat"
        }

    # 开发模式
    return {
        "qr_url": None,
        "scene_str": "quant_login",
        "mode": "mock",
        "message": "开发模式：使用 /api/auth/mock/login 接口登录"
    }


@router.post("/wechat/login")
async def wechat_login(request: WeChatLoginRequest):
    """微信登录：用授权code换取用户信息并签发JWT"""
    # 检查微信是否配置
    if not settings.WECHAT_APPID:
        return WeChatLoginResponse(
            success=False,
            error="wechat_not_configured",
            message="微信未配置，请使用开发模式登录: POST /api/auth/mock/login"
        )

    try:
        import wechatpy

        client = wechatpy.WeChatOAuth(
            app_id=settings.WECHAT_APPID,
            secret=settings.WECHAT_APPSECRET,
            redirect_uri=""
        )
        result = client.fetch_access_token(request.code)
        openid = result.get("openid")

        if not openid:
            return WeChatLoginResponse(success=False, error="invalid_code")

        # 查找或创建用户
        async with AsyncSessionLocal() as session:
            stmt = select(User).where(User.openid == openid)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    openid=openid,
                    nickname=result.get("nickname", "用户"),
                    avatar_url=result.get("headimgurl", "")
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

        jwt_token = create_jwt_token(openid, user.nickname)

        return WeChatLoginResponse(
            success=True,
            user_id=openid,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            jwt_token=jwt_token,
            expires_in=604800
        )

    except Exception as e:
        logger.error(f"WeChat login error: {e}")
        return WeChatLoginResponse(success=False, error=str(e))


@router.post("/mock/login")
async def mock_login(request: MockLoginRequest):
    """开发模式模拟登录（不依赖微信）"""
    user_info = MOCK_USERS.get(request.user_id)

    if not user_info:
        return {
            "success": False,
            "error": "invalid_mock_user",
            "message": f"无效的用户ID。可用的开发用户: {list(MOCK_USERS.keys())}"
        }

    jwt_token = create_jwt_token(request.user_id, user_info["nickname"])

    return {
        "success": True,
        "user_id": request.user_id,
        "nickname": user_info["nickname"],
        "avatar_url": user_info["avatar_url"],
        "jwt_token": jwt_token,
        "expires_in": 604800,
        "mode": "mock"
    }


@router.get("/mock/users")
async def list_mock_users():
    """列出所有开发模式可用的模拟用户"""
    return {
        "success": True,
        "data": {
            "users": [
                {"user_id": uid, "nickname": info["nickname"]}
                for uid, info in MOCK_USERS.items()
            ],
            "login_endpoint": "/api/auth/mock/login",
            "method": "POST",
            "body": {"user_id": "dev_user_001"}
        }
    }


@router.get("/me")
async def get_me(authorization: str = None):
    """获取当前登录用户信息"""
    payload = get_current_user(authorization)
    return {
        "success": True,
        "data": {
            "user_id": payload.get("user_id"),
            "nickname": payload.get("nickname"),
            "avatar_url": None
        }
    }
