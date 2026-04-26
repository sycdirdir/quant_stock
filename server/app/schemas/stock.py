from pydantic import BaseModel
from typing import Optional, List, Any


class StockItem(BaseModel):
    ts_code: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    area: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    list_date: Optional[str] = None
    is_hs: Optional[str] = None


class StockListResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class KlineItem(BaseModel):
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None


class KlineDownloadResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
