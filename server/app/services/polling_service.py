"""
实时行情轮询服务
使用 RQSDK 获取实时行情并推送到 WebSocket
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional, List, Dict, Any
from app.services.stream_service import get_stream_service
from app.services.rqsdk_service import is_available, get_rqsdk_service

logger = logging.getLogger(__name__)


class MarketPollingService:
    """市场行情轮询服务"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._interval = 1  # 轮询间隔 (秒) - 优化为1秒
        self._last_quotes: Dict[str, Dict[str, Any]] = {}  # 缓存上次数据用于变化检测

    async def start(self):
        """启动轮询服务"""
        if self._running:
            return

        if not is_available():
            logger.warning("RQSDK 不可用，轮询服务无法启动")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("市场行情轮询服务启动")

    async def stop(self):
        """停止轮询服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("市场行情轮询服务停止")

    async def _poll_loop(self):
        """轮询循环"""
        from app.services.stream_service import manager

        while self._running:
            try:
                # 检查是否在交易时间
                if not self._is_trading_time():
                    await asyncio.sleep(60)  # 非交易时间一分钟检查一次
                    continue

                # 获取所有订阅的股票
                subscribed_codes = manager.get_subscribed_codes()

                if not subscribed_codes:
                    await asyncio.sleep(self._interval)
                    continue

                # 批量获取行情
                await self._fetch_and_push_quotes(subscribed_codes)

                await asyncio.sleep(self._interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"轮询错误: {e}")
                await asyncio.sleep(self._interval)

    async def _fetch_and_push_quotes(self, ts_codes: List[str]):
        """获取并推送行情"""
        try:
            service = get_rqsdk_service()
            if service is None:
                return

            # 批量获取实时行情
            quotes = service.get_realtime_quote(ts_codes)

            if not quotes:
                return

            stream = get_stream_service()

            # 推送每个股票的行情（仅当数据变化时）
            for ts_code, quote in quotes.items():
                # 格式化数据
                formatted_quote = {
                    "last": quote.get("last", 0),
                    "open": quote.get("open", 0),
                    "high": quote.get("high", 0),
                    "low": quote.get("low", 0),
                    "volume": quote.get("volume", 0),
                    "amount": quote.get("amount", 0),
                    "change": quote.get("change", 0),
                    "prev_close": quote.get("prev_close", 0),
                    "timestamp": datetime.now().isoformat()
                }

                # 检测数据是否变化
                last_quote = self._last_quotes.get(ts_code)
                if last_quote and self._is_quote_unchanged(last_quote, formatted_quote):
                    continue  # 数据未变化，跳过推送

                self._last_quotes[ts_code] = formatted_quote
                await stream.push_quote(ts_code, formatted_quote)

        except Exception as e:
            logger.error(f"获取行情失败: {e}")

    def _is_quote_unchanged(self, old: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """检测行情是否未变化"""
        # 关键字段比较
        keys = ["last", "open", "high", "low", "volume", "amount"]
        for key in keys:
            if old.get(key) != new.get(key):
                return False
        return True

    def _is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        now = datetime.now()
        current_time = now.time()

        # 周末
        if now.weekday() >= 5:
            return False

        # A 股交易时间: 9:30-11:30, 13:00-15:00
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)

        if morning_start <= current_time <= morning_end:
            return True
        if afternoon_start <= current_time <= afternoon_end:
            return True

        return False

    def set_interval(self, seconds: int):
        """设置轮询间隔"""
        self._interval = max(1, seconds)


# 全局轮询服务
polling_service: Optional[MarketPollingService] = None


def get_polling_service() -> MarketPollingService:
    """获取轮询服务实例"""
    global polling_service
    if polling_service is None:
        polling_service = MarketPollingService()
    return polling_service
