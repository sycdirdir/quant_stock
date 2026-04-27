"""
策略云端同步路由
支持策略的云端存储、版本管理、模板分享
"""

from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import json
import logging

from app.database import AsyncSessionLocal
from app.models.strategy import Strategy, StrategyVersion, StrategyTemplate
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud", tags=["云端同步"])


# ============ 请求/响应模型 ============

class StrategyItem(BaseModel):
    local_id: Optional[int] = None
    id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    config_json: str
    code: Optional[str] = ""
    version: int = 1
    updated_at: Optional[str] = None


class StrategySyncRequest(BaseModel):
    strategies: List[StrategyItem]
    mode: str = "full"  # full=全量同步, incremental=增量同步


class StrategySyncResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class StrategyListResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# ============ 辅助函数 ============

async def get_user_from_token(authorization: str = None) -> Optional[str]:
    """从 Authorization header 获取用户 ID"""
    if not authorization:
        return None
    # 简化处理，实际应该验证 JWT token
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            # 这里应该验证 JWT 并获取 user_id
            # 暂时返回简化结果
            return "user_" + token[:8]
    except:
        pass
    return None


# ============ 策略同步接口 ============

@router.post("/strategies/sync", response_model=StrategySyncResponse)
async def sync_strategies(
    request: StrategySyncRequest,
    authorization: str = Header(None)
):
    """
    同步策略到云端

    支持全量同步和增量同步
    - 全量同步: 客户端上传所有本地策略
    - 增量同步: 客户端上传自上次同步后修改的策略
    """
    user_id = await get_user_from_token(authorization)

    if not user_id:
        # 尝试从请求体获取 user_id (开发模式)
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            synced_results = []

            for strategy_item in request.strategies:
                # 检查是否已存在
                existing = None
                if strategy_item.id:
                    stmt = Strategy.__table__.select().where(
                        Strategy.id == strategy_item.id,
                        Strategy.user_id == user_id
                    )
                    result = await session.execute(stmt)
                    existing = result.fetchone()

                if existing:
                    # 更新已有策略
                    strategy_id = existing.id

                    # 创建版本记录
                    version_record = StrategyVersion(
                        strategy_id=strategy_id,
                        version=existing.version,
                        config_json=existing.config_json,
                        changelog=f"同步更新 {datetime.now().isoformat()}"
                    )
                    session.add(version_record)

                    # 更新策略
                    stmt = Strategy.__table__.update().where(
                        Strategy.id == strategy_id
                    ).values(
                        name=strategy_item.name,
                        description=strategy_item.description or "",
                        config_json=strategy_item.config_json,
                        code=strategy_item.code or "",
                        version=existing.version + 1,
                        synced=True,
                        last_synced_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    await session.execute(stmt)

                    synced_results.append({
                        "local_id": strategy_item.local_id,
                        "cloud_id": strategy_id,
                        "version": existing.version + 1,
                        "action": "updated"
                    })

                else:
                    # 创建新策略
                    new_strategy = Strategy(
                        user_id=user_id,
                        name=strategy_item.name,
                        description=strategy_item.description or "",
                        config_json=strategy_item.config_json,
                        code=strategy_item.code or "",
                        version=1,
                        synced=True,
                        last_synced_at=datetime.now()
                    )
                    session.add(new_strategy)
                    await session.flush()

                    synced_results.append({
                        "local_id": strategy_item.local_id,
                        "cloud_id": new_strategy.id,
                        "version": 1,
                        "action": "created"
                    })

            await session.commit()

            return StrategySyncResponse(
                success=True,
                data={
                    "synced": synced_results,
                    "synced_at": datetime.now().isoformat()
                }
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"策略同步失败: {e}")
            return StrategySyncResponse(success=False, error=str(e))


@router.get("/strategies", response_model=StrategyListResponse)
async def list_cloud_strategies(
    authorization: str = Header(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取云端策略列表"""
    user_id = await get_user_from_token(authorization)

    if not user_id:
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            # 查询用户的策略
            offset = (page - 1) * page_size

            stmt = Strategy.__table__.select().where(
                Strategy.user_id == user_id
            ).order_by(
                Strategy.updated_at.desc()
            ).limit(page_size).offset(offset)

            result = await session.execute(stmt)
            strategies = result.fetchall()

            # 查询总数
            count_stmt = Strategy.__table__.select().where(
                Strategy.user_id == user_id
            )
            count_result = await session.execute(count_stmt)
            total = len(count_result.fetchall())

            items = []
            for s in strategies:
                items.append({
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "version": s.version,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "synced": s.synced
                })

            return StrategyListResponse(
                success=True,
                data={
                    "strategies": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
            )

        except Exception as e:
            logger.error(f"获取云端策略失败: {e}")
            return StrategyListResponse(success=False, error=str(e))


@router.get("/strategies/{strategy_id}", response_model=StrategySyncResponse)
async def get_cloud_strategy(
    strategy_id: int,
    authorization: str = Header(None)
):
    """获取单个云端策略详情"""
    user_id = await get_user_from_token(authorization)

    if not user_id:
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            stmt = Strategy.__table__.select().where(
                Strategy.id == strategy_id,
                Strategy.user_id == user_id
            )
            result = await session.execute(stmt)
            strategy = result.fetchone()

            if not strategy:
                return StrategySyncResponse(
                    success=False,
                    error="策略不存在或无权访问"
                )

            return StrategySyncResponse(
                success=True,
                data={
                    "id": strategy.id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "config_json": strategy.config_json,
                    "code": strategy.code,
                    "version": strategy.version,
                    "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
                    "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None
                }
            )

        except Exception as e:
            logger.error(f"获取策略详情失败: {e}")
            return StrategySyncResponse(success=False, error=str(e))


@router.delete("/strategies/{strategy_id}", response_model=StrategySyncResponse)
async def delete_cloud_strategy(
    strategy_id: int,
    authorization: str = Header(None)
):
    """删除云端策略"""
    user_id = await get_user_from_token(authorization)

    if not user_id:
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            stmt = Strategy.__table__.delete().where(
                Strategy.id == strategy_id,
                Strategy.user_id == user_id
            )
            await session.execute(stmt)
            await session.commit()

            return StrategySyncResponse(
                success=True,
                data={"deleted": strategy_id}
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"删除策略失败: {e}")
            return StrategySyncResponse(success=False, error=str(e))


@router.get("/strategies/{strategy_id}/versions", response_model=StrategySyncResponse)
async def get_strategy_versions(
    strategy_id: int,
    authorization: str = Header(None)
):
    """获取策略版本历史"""
    user_id = await get_user_from_token(authorization)

    if not user_id:
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            # 检查策略所有权
            check_stmt = Strategy.__table__.select().where(
                Strategy.id == strategy_id,
                Strategy.user_id == user_id
            )
            result = await session.execute(check_stmt)
            if not result.fetchone():
                return StrategySyncResponse(success=False, error="策略不存在或无权访问")

            # 获取版本历史
            stmt = StrategyVersion.__table__.select().where(
                StrategyVersion.strategy_id == strategy_id
            ).order_by(StrategyVersion.version.desc())

            result = await session.execute(stmt)
            versions = result.fetchall()

            items = []
            for v in versions:
                items.append({
                    "version": v.version,
                    "config_json": v.config_json,
                    "changelog": v.changelog,
                    "created_at": v.created_at.isoformat() if v.created_at else None
                })

            return StrategySyncResponse(
                success=True,
                data={"versions": items}
            )

        except Exception as e:
            logger.error(f"获取版本历史失败: {e}")
            return StrategySyncResponse(success=False, error=str(e))


# ============ 策略模板接口 ============

@router.get("/templates", response_model=StrategyListResponse)
async def list_templates(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取公开策略模板"""
    async with AsyncSessionLocal() as session:
        try:
            offset = (page - 1) * page_size

            if category:
                stmt = StrategyTemplate.__table__.select().where(
                    StrategyTemplate.category == category
                ).order_by(
                    StrategyTemplate.use_count.desc()
                ).limit(page_size).offset(offset)
            else:
                stmt = StrategyTemplate.__table__.select().order_by(
                    StrategyTemplate.use_count.desc()
                ).limit(page_size).offset(offset)

            result = await session.execute(stmt)
            templates = result.fetchall()

            items = []
            for t in templates:
                items.append({
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "author": t.author,
                    "use_count": t.use_count,
                    "config_json": t.config_json
                })

            return StrategyListResponse(
                success=True,
                data={
                    "templates": items,
                    "page": page,
                    "page_size": page_size
                }
            )

        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return StrategyListResponse(success=False, error=str(e))


@router.post("/strategies/from-template/{template_id}", response_model=StrategySyncResponse)
async def create_from_template(
    template_id: int,
    name: str = Query(...),
    authorization: str = Header(None)
):
    """从模板创建策略"""
    user_id = await get_user_from_token(authorization)

    if not user_id:
        user_id = "dev_user"

    async with AsyncSessionLocal() as session:
        try:
            # 获取模板
            stmt = StrategyTemplate.__table__.select().where(
                StrategyTemplate.id == template_id
            )
            result = await session.execute(stmt)
            template = result.fetchone()

            if not template:
                return StrategySyncResponse(success=False, error="模板不存在")

            # 创建策略
            new_strategy = Strategy(
                user_id=user_id,
                name=name,
                description=f"基于模板 {template.name} 创建",
                config_json=template.config_json,
                version=1,
                synced=True,
                last_synced_at=datetime.now()
            )
            session.add(new_strategy)
            await session.flush()

            # 增加模板使用计数
            update_stmt = StrategyTemplate.__table__.update().where(
                StrategyTemplate.id == template_id
            ).values(use_count=template.use_count + 1)
            await session.execute(update_stmt)

            await session.commit()

            return StrategySyncResponse(
                success=True,
                data={
                    "id": new_strategy.id,
                    "name": new_strategy.name,
                    "version": 1
                }
            )

        except Exception as e:
            await session.rollback()
            logger.error(f"从模板创建策略失败: {e}")
            return StrategySyncResponse(success=False, error=str(e))
