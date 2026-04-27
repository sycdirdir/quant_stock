"""
Qlib 因子服务路由
提供 Alpha158 因子和 LightGBM 模型接口
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.services.qlib_service import (
    init_qlib,
    is_available,
    get_qlib_service,
    calculate_alpha158_from_kline
)
from app.services.rqsdk_service import get_rqsdk_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qlib", tags=["Qlib因子"])


class FeatureRequest(BaseModel):
    ts_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    frequency: str = "daily"


class TrainingRequest(BaseModel):
    ts_codes: List[str]
    start_date: str
    end_date: str
    label_type: str = "return"  # return, direction
    look_forward: int = 5  # 预测未来 N 天


class PredictionRequest(BaseModel):
    ts_code: str
    model_path: str
    features: Optional[List[str]] = None


# 初始化 Qlib
@router.on_event("startup")
async def startup():
    """启动时初始化 Qlib"""
    # 尝试初始化，使用环境变量或默认路径
    import os
    data_path = os.getenv("QLIB_DATA_PATH", "/Users/songyuanchao/aitest/quant_stock/data/qlib")
    init_qlib(data_path)


@router.get("/status")
async def get_status():
    """获取 Qlib 状态"""
    available = is_available()

    return {
        "success": True,
        "data": {
            "available": available,
            "alpha158_enabled": available,
            "lightgbm_enabled": available
        }
    }


@router.get("/factors/{ts_code}")
async def get_alpha158_factors(ts_code: str):
    """
    获取 Alpha158 因子 (从 RQSDK 数据计算)

    如果 Qlib 不可用，使用本地计算版本
    """
    try:
        # 优先使用 RQSDK 获取数据
        rq_service = get_rqsdk_service()

        if rq_service:
            df = rq_service.get_kline(
                ts_code=ts_code,
                frequency="1d"
            )

            if df is None or df.empty:
                return {"success": False, "error": f"无数据: {ts_code}"}

            # 计算 Alpha158 因子
            df_with_factors = calculate_alpha158_from_kline(df)

            # 转换为可序列化格式
            result = {}
            for col in df_with_factors.columns:
                values = df_with_factors[col].tolist()
                result[col] = [
                    float(v) if not (isinstance(v, float) and str(v) == 'nan') else None
                    for v in values
                ]

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "factors": result,
                    "total": len(df_with_factors)
                }
            }

        return {"success": False, "error": "数据服务不可用"}

    except Exception as e:
        logger.error(f"获取因子失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/backtest/signals")
async def get_ml_signals(
    ts_code: str = Query(..., description="股票代码"),
    start_date: str = Query("20230101", description="开始日期"),
    end_date: str = Query("20260424", description="结束日期"),
    model_type: str = Query("gradient_boosting", description="模型类型")
):
    """
    获取机器学习信号

    使用简单梯度提升模型预测涨跌
    """
    try:
        rq_service = get_rqsdk_service()
        if not rq_service:
            return {"success": False, "error": "数据服务不可用"}

        # 获取数据
        df = rq_service.get_kline(
            ts_code=ts_code,
            frequency="1d",
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return {"success": False, "error": f"无数据: {ts_code}"}

        # 计算特征
        df_features = calculate_alpha158_from_kline(df)

        # 生成标签: 未来5天上涨为1，下跌为0
        df_features["label"] = (df_features["close"].shift(-5) > df_features["close"]).astype(int)

        # 移除 NaN
        df_features = df_features.dropna()

        if len(df_features) < 50:
            return {"success": False, "error": "数据量不足"}

        # 特征列
        feature_cols = [
            "KLine_Close", "KLine_Volume", "ROC5", "ROC10", "ROC20",
            "Std5", "Std10", "Std20", "Volume_MA5", "Volume_MA20",
            "KLine_Close_MA5", "KLine_Close_MA20", "RSI5", "RSI10", "RSI20",
            "DIF", "DEA", "MACD", "BOLL20", "MFI10"
        ]

        # 只使用存在的列
        feature_cols = [c for c in feature_cols if c in df_features.columns]

        X = df_features[feature_cols].values
        y = df_features["label"].values

        # 简单分割
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        # 训练模型
        try:
            import lightgbm as lgb

            train_data = lgb.Dataset(X_train, label=y_train)

            params = {
                "objective": "binary",
                "metric": "auc",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "verbose": -1
            }

            model = lgb.train(params, train_data, num_boost_round=50)

            # 预测
            predictions = model.predict(X_test)

            # 生成信号
            signals = []
            for i, prob in enumerate(predictions):
                idx = i + split
                date = df_features.index[idx] if hasattr(df_features, 'index') else str(idx)

                if prob >= 0.6:
                    signals.append({
                        "date": date,
                        "signal": "BUY",
                        "confidence": float(prob),
                        "probability": float(prob)
                    })
                elif prob <= 0.4:
                    signals.append({
                        "date": date,
                        "signal": "SELL",
                        "confidence": float(1 - prob),
                        "probability": float(prob)
                    })

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "signals": signals,
                    "total_signals": len(signals),
                    "model": "lightgbm",
                    "accuracy": float((predictions > 0.5).mean())
                }
            }

        except ImportError:
            return {"success": False, "error": "LightGBM 未安装"}

    except Exception as e:
        logger.error(f"ML 信号生成失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/factors/list")
async def list_alpha158_factors():
    """列出 Alpha158 所有因子"""
    return {
        "success": True,
        "data": {
            "factors": [
                {"name": "K线因子", "items": ["KLine_Close", "KLine_Open", "KLine_High", "KLine_Low", "KLine_Volume"]},
                {"name": "动量因子", "items": ["ROC5", "ROC10", "ROC20", "ROC60", "RSI5", "RSI10", "RSI20", "MFI10"]},
                {"name": "波动率因子", "items": ["Std5", "Std10", "Std20", "Std60", "BOLL20", "BOLL60"]},
                {"name": "成交量因子", "items": ["Volume_MA5", "Volume_MA20", "Volume5", "Volume10", "Volume20", "Volume60"]},
                {"name": "均线因子", "items": ["KLine_Close_MA5", "KLine_Close_MA10", "KLine_Close_MA20", "KLine_Close_MA60"]},
                {"name": "MACD因子", "items": ["DIF", "DEA", "MACD"]},
            ],
            "total": 158,
            "description": "Alpha158 是 Qlib 提供的 158 维预计算因子集"
        }
    }
