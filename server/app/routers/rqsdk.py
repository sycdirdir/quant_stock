"""
RQSDK 数据接口路由
提供 RQSDK 数据服务 API
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.services.rqsdk_service import (
    init_rqdatac,
    is_available,
    get_rqsdk_service
)
from app.services.indicators import get_indicator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rqsdk", tags=["RQSDK数据"])


class StockListResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class KlineDataResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class IndicatorRequest(BaseModel):
    ts_code: str
    indicators: List[str]
    params: Optional[dict] = None


class SignalRequest(BaseModel):
    ts_code: str
    strategy_type: str = "ma_cross"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# 初始化 RQSDK
@router.on_event("startup")
async def startup():
    """启动时初始化 RQSDK"""
    success = init_rqdatac()
    if success:
        logger.info("RQSDK 初始化成功")
    else:
        logger.warning("RQSDK 初始化失败，部分功能不可用")


@router.get("/status")
async def get_status():
    """获取 RQSDK 连接状态"""
    available = is_available()
    service = get_rqsdk_service() if available else None

    return {
        "success": True,
        "data": {
            "available": available,
            "has_service": service is not None
        }
    }


@router.get("/stocks", response_model=StockListResponse)
async def get_stock_list(market: str = Query("a", description="市场: a=A股, hk=港股")):
    """获取股票列表"""
    if not is_available():
        return StockListResponse(success=False, error="RQSDK 未初始化")

    service = get_rqsdk_service()
    if service is None:
        return StockListResponse(success=False, error="RQSDK 服务不可用")

    try:
        stocks = service.get_stock_list(market=market)
        return StockListResponse(
            success=True,
            data={
                "total": len(stocks),
                "items": stocks
            }
        )
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return StockListResponse(success=False, error=str(e))


@router.get("/kline/{ts_code}", response_model=KlineDataResponse)
async def get_kline(
    ts_code: str,
    frequency: str = Query("daily", description="周期: daily/1m/5m/15m/30m/60m"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("none", description="复权: none/fwd/bwd")
):
    """获取K线数据"""
    if not is_available():
        return KlineDataResponse(success=False, error="RQSDK 未初始化")

    service = get_rqsdk_service()
    if service is None:
        return KlineDataResponse(success=False, error="RQSDK 服务不可用")

    try:
        # 转换频率格式
        freq_map = {
            "daily": "1d",
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
        }
        freq = freq_map.get(frequency, "1d")

        df = service.get_kline(
            ts_code=ts_code,
            frequency=freq,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust
        )

        if df is None or df.empty:
            return KlineDataResponse(success=False, error=f"无数据: {ts_code}")

        # 转换为列表格式
        items = []
        for _, row in df.iterrows():
            items.append({
                "trade_date": str(row.get("trade_date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
                "pre_close": float(row.get("pre_close", row.get("close", 0))),
            })

        return KlineDataResponse(
            success=True,
            data={
                "ts_code": ts_code,
                "frequency": frequency,
                "total": len(items),
                "items": items
            }
        )

    except Exception as e:
        logger.error(f"获取K线失败: {e}")
        return KlineDataResponse(success=False, error=str(e))


@router.get("/realtime/{ts_codes}")
async def get_realtime(
    ts_codes: str,
    ):
    """获取实时行情"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    service = get_rqsdk_service()
    if service is None:
        return {"success": False, "error": "RQSDK 服务不可用"}

    try:
        codes = ts_codes.split(",")
        quotes = service.get_realtime_quote(codes)
        return {
            "success": True,
            "data": quotes
        }
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/indicators")
async def calculate_indicators(request: IndicatorRequest):
    """计算技术指标"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    service = get_rqsdk_service()
    if service is None:
        return {"success": False, "error": "RQSDK 服务不可用"}

    try:
        # 获取K线数据
        df = service.get_kline(
            ts_code=request.ts_code,
            frequency="1d"
        )

        if df is None or df.empty:
            return {"success": False, "error": f"无数据: {request.ts_code}"}

        # 计算指标
        indicator_service = get_indicator_service()
        results = indicator_service.calculate(
            data=df,
            indicators=request.indicators,
            params=request.params or {}
        )

        # 转换结果为可序列化格式
        serialized = {}
        for name, values in results.items():
            serialized[name] = [float(v) if not np.isnan(v) else None for v in values]
        import numpy as np

        return {
            "success": True,
            "data": {
                "ts_code": request.ts_code,
                "indicators": serialized
            }
        }

    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/signals")
async def detect_signals(request: SignalRequest):
    """检测交易信号"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    service = get_rqsdk_service()
    if service is None:
        return {"success": False, "error": "RQSDK 服务不可用"}

    try:
        # 获取K线数据
        df = service.get_kline(
            ts_code=request.ts_code,
            frequency="1d",
            start_date=request.start_date,
            end_date=request.end_date
        )

        if df is None or df.empty:
            return {"success": False, "error": f"无数据: {request.ts_code}"}

        # 检测信号
        indicator_service = get_indicator_service()
        signals = indicator_service.detect_signals(
            data=df,
            strategy_type=request.strategy_type
        )

        return {
            "success": True,
            "data": {
                "ts_code": request.ts_code,
                "strategy_type": request.strategy_type,
                "signals": signals,
                "total": len(signals)
            }
        }

    except Exception as e:
        logger.error(f"检测信号失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/trading_dates")
async def get_trading_dates(
    market: str = Query("a", description="市场: a/hk"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    """获取交易日列表"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    service = get_rqsdk_service()
    if service is None:
        return {"success": False, "error": "RQSDK 服务不可用"}

    try:
        dates = service.get_trading_dates(
            market=market,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "success": True,
            "data": {
                "dates": dates,
                "total": len(dates)
            }
        }

    except Exception as e:
        logger.error(f"获取交易日失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/financial/{ts_code}")
async def get_financial(
    ts_code: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    """获取财务数据"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    service = get_rqsdk_service()
    if service is None:
        return {"success": False, "error": "RQSDK 服务不可用"}

    try:
        df = service.get_financial_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return {"success": True, "data": {"items": []}}

        # 转换为列表
        items = df.to_dict("records")

        return {
            "success": True,
            "data": {
                "ts_code": ts_code,
                "items": items,
                "total": len(items)
            }
        }

    except Exception as e:
        logger.error(f"获取财务数据失败: {e}")
        return {"success": False, "error": str(e)}
