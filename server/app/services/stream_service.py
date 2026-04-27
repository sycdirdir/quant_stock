"""
WebSocket 实时行情服务
支持 RQSDK tick 数据订阅和推送
"""

import asyncio
import json
import logging
from typing import Set, Dict, Any, Optional, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import threading

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 活跃连接
        self.active_connections: Set[WebSocket] = set()
        # 订阅关系: {ts_code: [websocket1, websocket2, ...]}
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        # 锁
        self.lock = asyncio.Lock()
        # RQSDK 轮询任务
        self._polling_task: Optional[asyncio.Task] = None
        self._running = False
        # 最新行情数据: {ts_code: data}
        self.latest_quotes: Dict[str, Dict[str, Any]] = {}
        # 增量更新缓存: {ts_code: set of changed fields}
        self._quote_changes: Dict[str, set] = {}
        # 批量推送定时器
        self._batch_task: Optional[asyncio.Task] = None
        self._batch_interval = 0.5  # 500ms 批量推送

    async def connect(self, websocket: WebSocket) -> bool:
        """接受新连接"""
        try:
            await websocket.accept()
            async with self.lock:
                self.active_connections.add(websocket)
            logger.info(f"WebSocket 连接建立，当前活跃: {len(self.active_connections)}")
            return True
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            return False

    async def disconnect(self, websocket: WebSocket):
        """断开连接"""
        async with self.lock:
            self.active_connections.discard(websocket)
            # 清理订阅
            for ts_code in list(self.subscriptions.keys()):
                self.subscriptions[ts_code].discard(websocket)
                if not self.subscriptions[ts_code]:
                    del self.subscriptions[ts_code]
        logger.info(f"WebSocket 断开，当前活跃: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, ts_codes: List[str]):
        """订阅股票行情"""
        async with self.lock:
            for ts_code in ts_codes:
                if ts_code not in self.subscriptions:
                    self.subscriptions[ts_code] = set()
                self.subscriptions[ts_code].add(websocket)
        logger.info(f"订阅: {ts_codes}, 当前订阅: {list(self.subscriptions.keys())}")

    async def unsubscribe(self, websocket: WebSocket, ts_codes: List[str]):
        """取消订阅"""
        async with self.lock:
            for ts_code in ts_codes:
                if ts_code in self.subscriptions:
                    self.subscriptions[ts_code].discard(websocket)
                    if not self.subscriptions[ts_code]:
                        del self.subscriptions[ts_code]
        logger.info(f"取消订阅: {ts_codes}")

    async def broadcast(self, message: dict, ts_codes: List[str] = None):
        """广播消息"""
        targets = set()

        if ts_codes:
            # 只发送给订阅了这些股票的连接
            for code in ts_codes:
                if code in self.subscriptions:
                    targets.update(self.subscriptions[code])
        else:
            # 发送给所有连接
            targets = self.active_connections.copy()

        disconnected = set()
        for connection in targets:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # 清理断开的连接
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_to_all(self, message: dict):
        """发送给所有连接"""
        await self.broadcast(message)

    def update_quote(self, ts_code: str, quote: Dict[str, Any]):
        """更新最新行情并追踪变化字段"""
        old_quote = self.latest_quotes.get(ts_code, {})
        changed_fields = set()

        # 检测变化的字段
        for key, value in quote.items():
            if old_quote.get(key) != value:
                changed_fields.add(key)

        self.latest_quotes[ts_code] = quote
        if changed_fields:
            if ts_code not in self._quote_changes:
                self._quote_changes[ts_code] = set()
            self._quote_changes[ts_code].update(changed_fields)

    def get_quote_delta(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取增量更新"""
        if ts_code not in self._quote_changes:
            return None

        changes = self._quote_changes[ts_code]
        if not changes:
            return None

        full_quote = self.latest_quotes.get(ts_code, {})
        delta = {k: full_quote[k] for k in changes if k in full_quote}
        delta["_changed_fields"] = list(changes)
        return delta

    def clear_changes(self, ts_code: str):
        """清除已推送的变化"""
        self._quote_changes.pop(ts_code, None)

    def get_latest_quote(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取最新行情"""
        return self.latest_quotes.get(ts_code)

    def get_subscribed_codes(self) -> List[str]:
        """获取所有订阅的股票代码"""
        return list(self.subscriptions.keys())

    def get_active_count(self) -> int:
        """获取活跃连接数"""
        return len(self.active_connections)


# 全局连接管理器
manager = ConnectionManager()


class StreamService:
    """实时行情流服务"""

    def __init__(self):
        self.manager = manager
        self._running = False

    async def start(self):
        """启动服务"""
        if self._running:
            return
        self._running = True
        logger.info("实时行情流服务启动")

    async def stop(self):
        """停止服务"""
        self._running = False
        if self.manager._polling_task:
            self.manager._polling_task.cancel()
        logger.info("实时行情流服务停止")

    async def handle_websocket(self, websocket: WebSocket):
        """处理 WebSocket 连接"""
        if not await self.manager.connect(websocket):
            return

        try:
            # 发送欢迎消息
            await websocket.send_json({
                "type": "connected",
                "data": {
                    "server_time": datetime.now().isoformat(),
                    "active_connections": self.manager.get_active_count()
                }
            })

            # 消息循环
            while True:
                try:
                    # 等待客户端消息 (超时 30 秒)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )

                    msg = json.loads(data)
                    await self.handle_message(websocket, msg)

                except asyncio.TimeoutError:
                    # 发送心跳
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now().isoformat()
                    })

        except WebSocketDisconnect:
            logger.info("客户端断开连接")
        except Exception as e:
            logger.error(f"WebSocket 错误: {e}")
        finally:
            await self.manager.disconnect(websocket)

    async def handle_message(self, websocket: WebSocket, msg: dict):
        """处理客户端消息"""
        msg_type = msg.get("type", "")

        if msg_type == "subscribe":
            ts_codes = msg.get("ts_codes", [])
            await self.manager.subscribe(websocket, ts_codes)
            await websocket.send_json({
                "type": "subscribed",
                "ts_codes": ts_codes
            })

        elif msg_type == "unsubscribe":
            ts_codes = msg.get("ts_codes", [])
            await self.manager.unsubscribe(websocket, ts_codes)
            await websocket.send_json({
                "type": "unsubscribed",
                "ts_codes": ts_codes
            })

        elif msg_type == "get_quotes":
            ts_codes = msg.get("ts_codes", [])
            quotes = {}
            for code in ts_codes:
                q = self.manager.get_latest_quote(code)
                if q:
                    quotes[code] = q
            await websocket.send_json({
                "type": "quotes",
                "data": quotes
            })

        elif msg_type == "pong":
            # 心跳响应
            pass

        else:
            logger.warning(f"未知消息类型: {msg_type}")

    async def push_quote(self, ts_code: str, quote: Dict[str, Any], use_delta: bool = True):
        """推送行情到订阅者"""
        # 更新最新行情
        self.manager.update_quote(ts_code, quote)

        if use_delta and ts_code in self.manager._quote_changes:
            # 发送增量更新
            delta = self.manager.get_quote_delta(ts_code)
            if delta:
                await self.manager.broadcast(
                    {
                        "type": "quote_delta",
                        "ts_code": ts_code,
                        "data": delta,
                        "timestamp": datetime.now().isoformat()
                    },
                    ts_codes=[ts_code]
                )
                self.manager.clear_changes(ts_code)
        else:
            # 发送完整数据
            await self.manager.broadcast(
                {
                    "type": "quote",
                    "ts_code": ts_code,
                    "data": quote,
                    "timestamp": datetime.now().isoformat()
                },
                ts_codes=[ts_code]
            )

    async def push_kline(self, ts_code: str, kline: Dict[str, Any]):
        """推送 K 线更新"""
        await self.manager.broadcast(
            {
                "type": "kline",
                "ts_code": ts_code,
                "data": kline,
                "timestamp": datetime.now().isoformat()
            },
            ts_codes=[ts_code]
        )

    async def push_signal(self, ts_code: str, signal: Dict[str, Any]):
        """推送交易信号"""
        await self.manager.broadcast(
            {
                "type": "signal",
                "ts_code": ts_code,
                "data": signal,
                "timestamp": datetime.now().isoformat()
            },
            ts_codes=[ts_code]
        )


# 全局服务实例
stream_service: Optional[StreamService] = None


def get_stream_service() -> StreamService:
    """获取流服务实例"""
    global stream_service
    if stream_service is None:
        stream_service = StreamService()
    return stream_service
