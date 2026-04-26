from fastapi import APIRouter, Query
from typing import Optional
from app.schemas.stock import StockListResponse
from app.database import AsyncSessionLocal
from sqlalchemy import text

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("", response_model=StockListResponse)
async def list_stocks(
    search: Optional[str] = Query(None, description="搜索名称/代码"),
    market: Optional[str] = Query(None, description="市场筛选"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """获取股票列表，支持搜索和分页"""
    try:
        async with AsyncSessionLocal() as session:
            # 构建 WHERE 条件
            where_parts = []
            params: dict = {}

            if search:
                where_parts.append("(name ILIKE :search OR ts_code ILIKE :search OR symbol ILIKE :search)")
                params["search"] = f"%{search}%"

            if market:
                where_parts.append("market = :market")
                params["market"] = market

            if industry:
                where_parts.append("industry = :industry")
                params["industry"] = industry

            where_sql = " AND ".join(where_parts) if where_parts else "1=1"

            # 查询总数
            count_sql = f"SELECT COUNT(*) FROM stock_basic WHERE {where_sql}"
            result = await session.execute(text(count_sql), params)
            total = result.scalar() or 0

            # 查询列表
            offset = (page - 1) * page_size
            params["limit"] = page_size
            params["offset"] = offset

            query_sql = f"""
                SELECT ts_code, symbol, name, area, industry, market, list_date, is_hs
                FROM stock_basic
                WHERE {where_sql}
                ORDER BY ts_code
                LIMIT :limit OFFSET :offset
            """
            result = await session.execute(text(query_sql), params)
            rows = result.fetchall()

            items = [
                {
                    "ts_code": row[0],
                    "symbol": row[1],
                    "name": row[2],
                    "area": row[3],
                    "industry": row[4],
                    "market": row[5],
                    "list_date": row[6],
                    "is_hs": row[7]
                }
                for row in rows
            ]

            return StockListResponse(
                success=True,
                data={
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "items": items
                }
            )

    except Exception as e:
        return StockListResponse(success=False, error=str(e))
