"""
Redis 缓存服务
用于缓存热点股票数据，加速 K 线切换
参考 QuantMind 架构
"""

import json
from typing import Optional, List, Any
from app.config import RedisDB
from app.database import RedisManager


class CacheService:
    """缓存服务"""

    # 缓存 key 前缀
    PREFIX_KLINE = "kline:"
    PREFIX_STOCK_INFO = "stock:info:"
    PREFIX_MARKET_SNAPSHOT = "market:snapshot:"

    # 缓存过期时间 (秒)
    TTL_KLINE = 3600 * 24  # 1 天
    TTL_STOCK_INFO = 3600 * 24 * 7  # 7 天
    TTL_MARKET = 60  # 1 分钟

    @classmethod
    def _kline_key(cls, ts_code: str, period: str, start_date: str, end_date: str) -> str:
        """生成 K 线缓存 key"""
        return f"{cls.PREFIX_KLINE}{ts_code}:{period}:{start_date}:{end_date}"

    @classmethod
    async def get_kline(cls, ts_code: str, period: str, start_date: str, end_date: str) -> Optional[List[dict]]:
        """获取缓存的 K 线数据"""
        key = cls._kline_key(ts_code, period, start_date, end_date)
        try:
            client = await RedisManager.get_client(RedisDB.DB_MARKET)
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    @classmethod
    async def set_kline(
        cls,
        ts_code: str,
        period: str,
        start_date: str,
        end_date: str,
        data: List[dict]
    ) -> bool:
        """缓存 K 线数据"""
        key = cls._kline_key(ts_code, period, start_date, end_date)
        try:
            client = await RedisManager.get_client(RedisDB.DB_MARKET)
            await client.setex(key, cls.TTL_KLINE, json.dumps(data, ensure_ascii=False))
            return True
        except Exception:
            return False

    @classmethod
    async def invalidate_kline(cls, ts_code: str) -> int:
        """删除指定股票的所有 K 线缓存"""
        try:
            client = await RedisManager.get_client(RedisDB.DB_MARKET)
            pattern = f"{cls.PREFIX_KLINE}{ts_code}:*"
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception:
            return 0

    @classmethod
    async def get_stock_info(cls, ts_code: str) -> Optional[dict]:
        """获取缓存的股票信息"""
        key = f"{cls.PREFIX_STOCK_INFO}{ts_code}"
        try:
            client = await RedisManager.get_client(RedisDB.DB_GENERAL)
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    @classmethod
    async def set_stock_info(cls, ts_code: str, info: dict) -> bool:
        """缓存股票信息"""
        key = f"{cls.PREFIX_STOCK_INFO}{ts_code}"
        try:
            client = await RedisManager.get_client(RedisDB.DB_GENERAL)
            await client.setex(key, cls.TTL_STOCK_INFO, json.dumps(info, ensure_ascii=False))
            return True
        except Exception:
            return False

    @classmethod
    async def get_market_snapshot(cls, date: str) -> Optional[dict]:
        """获取市场快照"""
        key = f"{cls.PREFIX_MARKET_SNAPSHOT}{date}"
        try:
            client = await RedisManager.get_client(RedisDB.DB_MARKET)
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    @classmethod
    async def set_market_snapshot(cls, date: str, snapshot: dict) -> bool:
        """缓存市场快照"""
        key = f"{cls.PREFIX_MARKET_SNAPSHOT}{date}"
        try:
            client = await RedisManager.get_client(RedisDB.DB_MARKET)
            await client.setex(key, cls.TTL_MARKET, json.dumps(snapshot, ensure_ascii=False))
            return True
        except Exception:
            return False

    @classmethod
    async def increment_backtest_count(cls, strategy_id: str) -> int:
        """增加回测计数 (用于热门策略统计)"""
        try:
            client = await RedisManager.get_client(RedisDB.DB_BACKTEST)
            key = f"backtest:count:{strategy_id}"
            return await client.incr(key)
        except Exception:
            return 0

    @classmethod
    async def get_backtest_count(cls, strategy_id: str) -> int:
        """获取回测计数"""
        try:
            client = await RedisManager.get_client(RedisDB.DB_BACKTEST)
            key = f"backtest:count:{strategy_id}"
            count = await client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0

    @classmethod
    async def close_connection(cls):
        """关闭所有 Redis 连接"""
        await RedisManager.close_all()
