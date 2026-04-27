"""
WebSocket 实时行情路由
提供 WebSocket 连接端点
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.stream_service import get_stream_service
from app.services.polling_service import get_polling_service
from app.services.rqsdk_service import is_available
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket 实时行情连接

    客户端消息格式:
    {
        "type": "subscribe",
        "ts_codes": ["000001.XSHG", "600000.XSHG"]
    }

    {
        "type": "unsubscribe",
        "ts_codes": ["000001.XSHG"]
    }

    {
        "type": "get_quotes",
        "ts_codes": ["000001.XSHG"]
    }

    服务端推送格式:
    {
        "type": "quote",
        "ts_code": "000001.XSHG",
        "data": {
            "last": 12.34,
            "open": 12.00,
            "high": 12.50,
            "low": 11.80,
            "volume": 1234567,
            "change": 2.5
        },
        "timestamp": "2024-01-01T10:30:00"
    }
    """
    stream_service = get_stream_service()

    # 启动轮询服务 (如果 RQSDK 可用)
    if is_available():
        polling = get_polling_service()
        await polling.start()

    await stream_service.handle_websocket(websocket)


@router.get("/api/stream/status")
async def get_stream_status():
    """获取流服务状态"""
    from app.services.stream_service import manager

    return {
        "success": True,
        "data": {
            "active_connections": manager.get_active_count(),
            "subscribed_codes": manager.get_subscribed_codes(),
            "rqsdk_available": is_available()
        }
    }
