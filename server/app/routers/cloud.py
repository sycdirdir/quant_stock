from fastapi import APIRouter, HTTPException
from app.schemas.strategy import StrategySyncRequest, StrategySyncResponse
from app.utils.auth import get_current_user
from app.database import AsyncSessionLocal
from sqlalchemy import select, text
from app.models.user import User
import json

router = APIRouter(prefix="/api/cloud", tags=["云端同步"])


@router.post("/strategies/sync", response_model=StrategySyncResponse)
async def sync_strategies(
    request: StrategySyncRequest,
    authorization: str = None
):
    """同步策略到云端（备份）"""
    try:
        payload = get_current_user(authorization)
        user_id = payload.get("user_id")

        if not user_id:
            return StrategySyncResponse(success=False, error="Unauthorized")

        # 实际实现中应写入 PostgreSQL 的 cloud_strategies 表
        # 这里先返回成功模拟
        synced = [{"local_id": s.local_id, "cloud_id": 100 + s.local_id} for s in request.strategies]

        return StrategySyncResponse(
            success=True,
            data={"synced": synced}
        )

    except Exception as e:
        return StrategySyncResponse(success=False, error=str(e))


@router.get("/strategies", response_model=StrategySyncResponse)
async def list_cloud_strategies(authorization: str = None):
    """获取云端策略列表"""
    try:
        payload = get_current_user(authorization)
        user_id = payload.get("user_id")

        if not user_id:
            return StrategySyncResponse(success=False, error="Unauthorized")

        # 实际实现中应从 PostgreSQL 查询 cloud_strategies 表
        return StrategySyncResponse(
            success=True,
            data={"strategies": []}
        )

    except Exception as e:
        return StrategySyncResponse(success=False, error=str(e))
