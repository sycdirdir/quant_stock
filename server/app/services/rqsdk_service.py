"""
RQSDK 数据服务
封装 RiceQuant RQData API，提供统一的数据接口
支持：日线/分钟/tick/实时/财务数据
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
import pandas as pd

logger = logging.getLogger(__name__)

# RQSDK 异步初始化标志
_rq_initialized = False


def init_rqdatac():
    """初始化 RQSDK 连接"""
    global _rq_initialized
    if _rq_initialized:
        return True

    try:
        import rqdatac as rq
        # 配置RQSDK (如果需要)
        # rq.init()
        _rq_initialized = True
        logger.info("RQSDK 初始化成功")
        return True
    except Exception as e:
        logger.warning(f"RQSDK 初始化失败: {e}")
        return False


def is_available() -> bool:
    """检查 RQSDK 是否可用"""
    return _rq_initialized


class RQSDKService:
    """RQSDK 数据服务封装"""

    def __init__(self):
        import rqdatac as rq
        self.rq = rq

    def get_stock_list(self, market: str = "a") -> List[Dict[str, Any]]:
        """
        获取股票列表

        Args:
            market: "a"=A股, "hk"=港股

        Returns:
            股票列表 [{ts_code, symbol, name, ...}]
        """
        try:
            df = self.rq.all_instruments(type="stock", market=market)
            if df is None or df.empty:
                return []

            # 转换为我们的格式
            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": row.get("order_book_id", ""),
                    "symbol": row.get("order_book_id", ""),
                    "name": row.get("symbol", ""),
                    "area": row.get("board", ""),
                    "industry": "",
                    "market": market.upper(),
                    "list_date": row.get("listed_date", "").strftime("%Y%m%d") if hasattr(row.get("listed_date", ""), 'strftime') else str(row.get("listed_date", "")),
                })
            return result
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def get_kline(
        self,
        ts_code: str,
        frequency: str = "1d",
        start_date: Union[str, date] = None,
        end_date: Union[str, date] = None,
        adjust_type: str = "none"
    ) -> pd.DataFrame:
        """
        获取 K 线数据

        Args:
            ts_code: 股票代码 (如 "000001.XSHG")
            frequency: "1d"=日线, "1m"=1分钟, "5m"=5分钟, "1h"=1小时
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期
            adjust_type: "none"=不复权, "fwd"=前复权, "bwd"=后复权

        Returns:
            DataFrame with columns: trade_date, open, high, low, close, volume
        """
        try:
            # 转换日期格式
            if start_date:
                start_date = str(start_date)
                if len(start_date) == 8:
                    start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if end_date:
                end_date = str(end_date)
                if len(end_date) == 8:
                    end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

            # 转换频率
            freq_map = {
                "1d": "1d",
                "daily": "1d",
                "1m": "1m",
                "1min": "1m",
                "5m": "5m",
                "5min": "5m",
                "15m": "15m",
                "15min": "15m",
                "30m": "30m",
                "30min": "30m",
                "60m": "60m",
                "60min": "60m",
                "1h": "60m",
            }
            freq = freq_map.get(frequency, "1d")

            df = self.rq.get_price(
                order_book_id=ts_code,
                start_date=start_date,
                end_date=end_date,
                frequency=freq,
                adjust_type=adjust_type
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # 转换为我们需要的格式
            result = pd.DataFrame()
            result["trade_date"] = df.index.strftime("%Y%m%d") if hasattr(df.index, 'strftime') else df.index
            result["open"] = df["open"].values
            result["high"] = df["high"].values
            result["low"] = df["low"].values
            result["close"] = df["close"].values
            result["volume"] = df["volume"].values

            if "prev_close" in df.columns:
                result["pre_close"] = df["prev_close"].values

            return result

        except Exception as e:
            logger.error(f"获取K线失败 {ts_code}: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, ts_codes: List[str]) -> Dict[str, Any]:
        """
        获取实时行情

        Args:
            ts_codes: 股票代码列表

        Returns:
            {ts_code: {last, open, high, low, volume, ...}}
        """
        try:
            df = self.rq.get_market_snapshot(ts_codes)
            if df is None or df.empty:
                return {}

            result = {}
            for _, row in df.iterrows():
                code = row.get("order_book_id", "")
                result[code] = {
                    "last": row.get("last", 0),
                    "open": row.get("open", 0),
                    "high": row.get("high", 0),
                    "low": row.get("low", 0),
                    "volume": row.get("volume", 0),
                    "amount": row.get("turnover", 0),
                    "change": row.get("change_pct", 0),
                    "prev_close": row.get("prev_close", 0),
                }
            return result

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {}

    def get_financial_data(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None,
        fields: List[str] = None
    ) -> pd.DataFrame:
        """
        获取财务数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 字段列表 (如 ["pe_ttm", "pb", "roe"])

        Returns:
            DataFrame with financial indicators
        """
        try:
            if fields is None:
                fields = ["pe_ttm", "pb", "ps_ttm", "roe", "roa", "debt_to_assets"]

            df = self.rq.get_financials(
                order_book_id=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )

            return df if df is not None else pd.DataFrame()

        except Exception as e:
            logger.error(f"获取财务数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def get_trading_dates(
        self,
        market: str = "a",
        start_date: str = None,
        end_date: str = None
    ) -> List[str]:
        """
        获取交易日列表

        Args:
            market: "a"=A股, "hk"=港股
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日列表 ["20240101", "20240102", ...]
        """
        try:
            dates = self.rq.get_trading_dates(
                market=market,
                start_date=start_date,
                end_date=end_date
            )

            if dates is None:
                return []

            return [d.strftime("%Y%m%d") if hasattr(d, 'strftime') else str(d) for d in dates]

        except Exception as e:
            logger.error(f"获取交易日失败: {e}")
            return []

    def get_future_main_contract(self, underlying: str = "IF") -> str:
        """
        获取期货主力合约

        Args:
            underlying: 期货品种 (如 "IF", "IC", "IH", "IM")

        Returns:
            主力合约代码 (如 "IF2301")
        """
        try:
            contract = self.rq.main_contract(underlying=underlying)
            return contract if contract else ""
        except Exception as e:
            logger.error(f"获取期货主力合约失败: {e}")
            return ""

    def get_dividends(self, ts_code: str) -> pd.DataFrame:
        """
        获取分红送股数据

        Args:
            ts_code: 股票代码

        Returns:
            DataFrame with dividend data
        """
        try:
            df = self.rq.get_dividends(order_book_id=ts_code)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取分红数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def get_split(self, ts_code: str) -> pd.DataFrame:
        """
        获取拆股并股数据

        Args:
            ts_code: 股票代码

        Returns:
            DataFrame with split data
        """
        try:
            df = self.rq.get_split(order_book_id=ts_code)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取拆股数据失败 {ts_code}: {e}")
            return pd.DataFrame()

    def get_index_weights(self, index_code: str, date: str = None) -> pd.DataFrame:
        """
        获取指数成分股权重

        Args:
            index_code: 指数代码 (如 "000300.XSHG"=沪深300)
            date: 日期

        Returns:
            DataFrame with {order_book_id, weight}
        """
        try:
            df = self.rq.get_index_weights(
                index=index_code,
                date=date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取指数权重失败 {index_code}: {e}")
            return pd.DataFrame()

    def get_shsz_margin(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取沪深融资融券数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with margin trading data
        """
        try:
            df = self.rq.get_shsz_margin(
                start_date=start_date,
                end_date=end_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return pd.DataFrame()

    def subscribe(self, ts_codes: List[str], frequency: str = "tick"):
        """
        订阅实时行情 (用于 WebSocket 推送)

        Args:
            ts_codes: 股票代码列表
            frequency: "tick"=tick, "1m"=1分钟

        Returns:
            True if success
        """
        try:
            self.rq.subscribe(ts_codes, frequency)
            return True
        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False

    def unsubscribe(self, ts_codes: List[str]):
        """
        取消订阅

        Args:
            ts_codes: 股票代码列表
        """
        try:
            self.rq.unsubscribe(ts_codes)
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")


# 全局服务实例
_service: Optional[RQSDKService] = None


def get_rqsdk_service() -> Optional[RQSDKService]:
    """获取 RQSDK 服务实例 (懒加载)"""
    global _service
    if _service is None and _rq_initialized:
        _service = RQSDKService()
    return _service
