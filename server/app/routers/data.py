from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.schemas.stock import KlineDownloadResponse, KlineItem
from app.schemas.strategy import StrategySyncRequest, StrategySyncResponse
from app.utils.auth import get_current_user
from app.database import AsyncSessionLocal
from sqlalchemy import select, text
from app.models.user import User
from app.models.data_update import DataUpdateRecord
import json

router = APIRouter(prefix="/api/data", tags=["数据"])


@router.get("/download/{ts_code}", response_model=KlineDownloadResponse)
async def download_kline(
    ts_code: str,
    period: str = Query(..., description="daily|weekly|monthly"),
    start_date: str = Query(..., description="YYYYMMDD"),
    end_date: str = Query(..., description="YYYYMMDD")
):
    """下载K线数据"""
    valid_periods = {
        "daily": "daily",
        "weekly": "stock_weekly",
        "monthly": "stock_monthly"
    }

    table_name = valid_periods.get(period)
    if not table_name:
        return KlineDownloadResponse(success=False, error=f"Invalid period: {period}")

    date_col = "trade_date" if period == "daily" else "trade_date"

    try:
        async with AsyncSessionLocal() as session:
            sql = text(f"""
                SELECT
                    trade_date,
                    open::float,
                    high::float,
                    low::float,
                    close::float,
                    pre_close::float,
                    change::float,
                    pct_chg::float,
                    vol::float,
                    amount::float
                FROM {table_name}
                WHERE ts_code = :ts_code
                  AND {date_col} >= :start_date
                  AND {date_col} <= :end_date
                ORDER BY {date_col} ASC
            """)

            result = await session.execute(sql, {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            })
            rows = result.fetchall()

            items = []
            for row in rows:
                items.append({
                    "trade_date": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "pre_close": row[5],
                    "change": row[6],
                    "pct_chg": row[7],
                    "vol": row[8],
                    "amount": row[9]
                })

            return KlineDownloadResponse(
                success=True,
                data={
                    "ts_code": ts_code,
                    "period": period,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total": len(items),
                    "items": items
                }
            )

    except Exception as e:
        return KlineDownloadResponse(success=False, error=str(e))


@router.get("/updates")
async def get_updates(
    since: Optional[str] = Query(None, description="YYYYMMDD，返回此日期后的增量")
):
    """获取数据增量更新列表"""
    try:
        async with AsyncSessionLocal() as session:
            if since:
                stmt = select(DataUpdateRecord).where(
                    DataUpdateRecord.update_date >= since
                ).order_by(DataUpdateRecord.update_date.desc())
            else:
                stmt = select(DataUpdateRecord).order_by(
                    DataUpdateRecord.update_date.desc()
                ).limit(30)

            result = await session.execute(stmt)
            records = result.scalars().all()

            updates = [
                {
                    "date": r.update_date,
                    "updated_stocks": json.loads(r.updated_stocks) if r.updated_stocks else [],
                    "version": r.version
                }
                for r in records
            ]

            return {"success": True, "data": {"updates": updates}}

    except Exception as e:
        return {"success": False, "error": str(e)}
