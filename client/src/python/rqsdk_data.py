#!/usr/bin/env python3
"""
RQSDK 数据服务 (客户端版)
使用 RiceQuant RQData 获取金融数据
"""

import sys
import json
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局初始化标志
_rq_initialized = False


def init_rqdatac() -> bool:
    """初始化 RQSDK 连接"""
    global _rq_initialized
    if _rq_initialized:
        return True

    try:
        import rqdatac as rq
        # RQSDK 客户端通常已经自动初始化
        # 如果需要手动初始化: rq.init()
        _rq_initialized = True
        logger.info("RQSDK 初始化成功")
        return True
    except Exception as e:
        logger.warning(f"RQSDK 初始化失败: {e}")
        return False


def is_available() -> bool:
    """检查 RQSDK 是否可用"""
    return _rq_initialized


class RQSDKClient:
    """RQSDK 客户端"""

    def __init__(self):
        import rqdatac as rq
        self.rq = rq

    def get_stock_list(self, market: str = "a") -> List[Dict[str, Any]]:
        """获取股票列表"""
        try:
            df = self.rq.all_instruments(type="stock", market=market)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append({
                    "ts_code": row.get("order_book_id", ""),
                    "symbol": row.get("order_book_id", ""),
                    "name": row.get("symbol", ""),
                    "area": row.get("board", ""),
                    "industry": "",
                    "market": market.upper(),
                    "list_date": str(row.get("listed_date", ""))[:10].replace("-", "") if row.get("listed_date") else "",
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
    ) -> List[Dict[str, Any]]:
        """
        获取 K 线数据

        Args:
            ts_code: 股票代码 (如 "000001.XSHG")
            frequency: "1d"=日线, "1m"=1分钟, "5m"=5分钟, etc
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期
            adjust_type: "none"=不复权, "fwd"=前复权, "bwd"=后复权

        Returns:
            [{trade_date, open, high, low, close, volume}, ...]
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
                "1d": "1d", "daily": "1d",
                "1m": "1m", "1min": "1m",
                "5m": "5m", "5min": "5m",
                "15m": "15m", "15min": "15m",
                "30m": "30m", "30min": "30m",
                "60m": "60m", "60min": "60m",
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
                return []

            # 转换为列表格式
            items = []
            for idx, row in df.iterrows():
                trade_date = idx.strftime("%Y%m%d") if hasattr(idx, 'strftime') else str(idx)
                items.append({
                    "trade_date": trade_date,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                })
            return items

        except Exception as e:
            logger.error(f"获取K线失败 {ts_code}: {e}")
            return []

    def get_realtime_quote(self, ts_codes: List[str]) -> Dict[str, Any]:
        """获取实时行情"""
        try:
            df = self.rq.get_market_snapshot(ts_codes)
            if df is None or df.empty:
                return {}

            result = {}
            for _, row in df.iterrows():
                code = row.get("order_book_id", "")
                result[code] = {
                    "last": float(row.get("last", 0)),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "volume": float(row.get("volume", 0)),
                    "change": float(row.get("change_pct", 0)),
                }
            return result

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {}

    def get_trading_dates(
        self,
        market: str = "a",
        start_date: str = None,
        end_date: str = None
    ) -> List[str]:
        """获取交易日列表"""
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


def run_command(cmd: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行命令"""
    if not is_available():
        return {"success": False, "error": "RQSDK 未初始化"}

    client = RQSDKClient()

    if cmd == "get_stock_list":
        market = params.get("market", "a")
        stocks = client.get_stock_list(market)
        return {"success": True, "data": {"items": stocks, "total": len(stocks)}}

    elif cmd == "get_kline":
        ts_code = params.get("ts_code", "")
        frequency = params.get("frequency", "daily")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        adjust = params.get("adjust", "none")

        items = client.get_kline(
            ts_code=ts_code,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust
        )
        return {
            "success": True,
            "data": {
                "ts_code": ts_code,
                "frequency": frequency,
                "items": items,
                "total": len(items)
            }
        }

    elif cmd == "get_realtime":
        ts_codes = params.get("ts_codes", [])
        quotes = client.get_realtime_quote(ts_codes)
        return {"success": True, "data": quotes}

    elif cmd == "get_trading_dates":
        market = params.get("market", "a")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        dates = client.get_trading_dates(market, start_date, end_date)
        return {"success": True, "data": {"dates": dates, "total": len(dates)}}

    else:
        return {"success": False, "error": f"Unknown command: {cmd}"}


if __name__ == "__main__":
    # 初始化
    init_rqdatac()

    # 从 stdin 读取命令
    input_data = sys.stdin.read()
    if not input_data.strip():
        print(json.dumps({"success": False, "error": "Empty input"}))
        sys.exit(1)

    try:
        cmd_data = json.loads(input_data)
        cmd = cmd_data.get("command", "")
        params = cmd_data.get("params", {})

        result = run_command(cmd, params)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
