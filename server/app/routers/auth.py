from fastapi import APIRouter, HTTPException
from app.schemas.auth import WeChatLoginRequest, WeChatLoginResponse, UserInfo
from app.utils.jwt import create_jwt_token
from app.utils.auth import get_current_user
from app.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select
import logging

router = APIRouter(prefix="/api/auth", tags=["认证"])
logger = logging.getLogger(__name__)


@router.get("/wechat/qr")
async def get_wechat_qr():
    """获取微信登录二维码URL（用于前端展示）"""
    # 微信开放平台二维码URL，前端可据此生成二维码
    # 实际场景中需要调用微信接口获取scene_str和二维码
    return {
        "qr_url": "https://open.weixin.qq.com/connect/qrcode/qrcode_placeholder",
        "scene_str": "quant_login"
    }


@router.post("/wechat/login")
async def wechat_login(request: WeChatLoginRequest):
    """微信登录：用授权code换取用户信息并签发JWT"""
    try:
        import wechatpy

        if not wechatpy:
            return WeChatLoginResponse(
                success=False,
                error="wechatpy_not_configured"
            )

        client = wechatpy.WeChatOAuth(
            app_id="",
            secret="",
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
