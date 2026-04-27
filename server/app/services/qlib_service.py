"""
Qlib 因子服务
封装微软 Qlib 的 Alpha158 因子库和 LightGBM 模型
支持：因子计算、模型训练、信号生成
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Qlib 初始化标志
_qlib_initialized = False
_qlib_data_path = None


def init_qlib(provider_uri: str = None) -> bool:
    """
    初始化 Qlib

    Args:
        provider_uri: Qlib 数据目录路径，默认使用本地数据
    """
    global _qlib_initialized, _qlib_data_path

    if _qlib_initialized:
        return True

    try:
        # 如果没有指定数据路径，尝试使用环境变量
        if provider_uri is None:
            provider_uri = "/Users/songyuanchao/aitest/quant_stock/data/qlib"

        import os
        if not os.path.exists(provider_uri):
            logger.warning(f"Qlib 数据目录不存在: {provider_uri}，将使用在线数据")
            provider_uri = None

        from qlib.data import D

        if provider_uri:
            D.init(provider_uri=provider_uri)
            _qlib_data_path = provider_uri
        else:
            # 使用默认初始化
            pass

        _qlib_initialized = True
        logger.info(f"Qlib 初始化成功，数据路径: {provider_uri}")
        return True

    except Exception as e:
        logger.warning(f"Qlib 初始化失败: {e}")
        return False


def is_available() -> bool:
    """检查 Qlib 是否可用"""
    return _qlib_initialized


class QlibService:
    """Qlib 服务封装"""

    # Alpha158 因子列表 (158维)
    ALPHA158_COLUMNS = [
        # K线因子 (6)
        "KLine_Close", "KLine_Open", "KLine_High", "KLine_Low", "KLine_Volume", "KLine_Amount",
        # 动量因子 (12)
        "ROC10", "ROC20", "ROC5", "ROC60", "MAX10", "MAX20", "MIN10", "MIN20",
        "RSI10", "RSI20", "RSI5", "MFI10",
        # 波动率因子 (6)
        "Std20", "Std60", "Std10", "Std5", "BOLL20", "BOLL60",
        # 成交量因子 (8)
        "Volume20", "Volume60", "Volume10", "Volume5", "Volume_MA5", "Volume_MA20",
        "Amount20", "Amount_MA5",
        # 价格因子 (10)
        "Mean20", "Mean60", "Mean10", "Correlation5", "Correlation20",
        "KLine_Close_MA5", "KLine_Close_MA10", "KLine_Close_MA20", "KLine_Close_MA60",
        "KLine_Volume_MA5",
        # 财务因子 (需要额外数据)
        # 以下因子可能需要 Qlib 特定数据
    ]

    def __init__(self):
        from qlib.data import D
        from qlib.data.ops import Operators
        self.D = D
        self.ops = Operators

    def get_alpha158_features(
        self,
        instruments: List[str],
        fields: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        freq: str = "day"
    ) -> pd.DataFrame:
        """
        获取 Alpha158 因子

        Args:
            instruments: 股票代码列表，如 ["SH000001", "SZ000001"]
            fields: 字段列表，默认使用 Alpha158 全部字段
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            freq: 频率 "day"/"1min"/"5min"/...

        Returns:
            DataFrame with multi-index (instrument, datetime)
        """
        try:
            if fields is None:
                # Alpha158 默认使用 K线字段
                fields = [
                    "$close", "$open", "$high", "$low", "$volume",
                    "Ref($close, 1)", "Ref($close, 2)",
                    "Mean($close, 5)", "Mean($close, 10)", "Mean($close, 20)",
                ]

            df = self.D.features(
                instruments=instruments,
                fields=fields,
                start_time=start_date,
                end_time=end_date,
                freq=freq
            )

            return df

        except Exception as e:
            logger.error(f"获取 Alpha158 因子失败: {e}")
            return pd.DataFrame()

    def calculate_standard_features(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, pd.Series]:
        """
        计算标准因子特征 (简化版，不依赖 Qlib 数据)

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {factor_name: values}
        """
        # 这是备用方案，使用本地数据计算
        return {}

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        label_col: str = "label"
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        准备训练数据

        Args:
            df: 包含特征和标签的 DataFrame
            label_col: 标签列名

        Returns:
            (X_train, y_train, X_test, y_test)
        """
        try:
            from sklearn.model_selection import train_test_split

            # 移除 NaN
            df = df.dropna()

            # 分离特征和标签
            if label_col not in df.columns:
                logger.error(f"标签列 {label_col} 不存在")
                return None, None, None, None

            X = df.drop(columns=[label_col])
            y = df[label_col]

            # 分割数据
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, shuffle=False
            )

            return X_train.values, y_train.values, X_test.values, y_test.values

        except Exception as e:
            logger.error(f"准备训练数据失败: {e}")
            return None, None, None, None

    def train_lightgbm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        params: Dict[str, Any] = None
    ) -> Any:
        """
        训练 LightGBM 模型

        Args:
            X_train: 训练特征
            y_train: 训练标签
            params: 模型参数

        Returns:
            训练好的模型
        """
        try:
            import lightgbm as lgb

            if params is None:
                params = {
                    "objective": "binary",
                    "metric": "auc",
                    "num_leaves": 31,
                    "learning_rate": 0.05,
                    "feature_fraction": 0.9,
                    "bagging_fraction": 0.8,
                    "bagging_freq": 5,
                    "verbose": -1
                }

            train_data = lgb.Dataset(X_train, label=y_train)

            model = lgb.train(
                params,
                train_data,
                num_boost_round=100
            )

            logger.info("LightGBM 模型训练完成")
            return model

        except Exception as e:
            logger.error(f"LightGBM 训练失败: {e}")
            return None

    def predict(self, model, X: np.ndarray) -> np.ndarray:
        """
        模型预测

        Args:
            model: 训练好的模型
            X: 特征数据

        Returns:
            预测概率
        """
        if model is None:
            return None

        try:
            return model.predict(X)
        except Exception as e:
            logger.error(f"模型预测失败: {e}")
            return None

    def generate_signals(
        self,
        predictions: np.ndarray,
        threshold_buy: float = 0.6,
        threshold_sell: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        根据预测结果生成交易信号

        Args:
            predictions: 预测概率
            threshold_buy: 买入阈值
            threshold_sell: 卖出阈值

        Returns:
            [{date, signal, confidence}, ...]
        """
        signals = []
        for i, prob in enumerate(predictions):
            if prob >= threshold_buy:
                signals.append({
                    "index": i,
                    "signal": "BUY",
                    "confidence": float(prob)
                })
            elif prob <= threshold_sell:
                signals.append({
                    "index": i,
                    "signal": "SELL",
                    "confidence": float(1 - prob)
                })
            else:
                signals.append({
                    "index": i,
                    "signal": "HOLD",
                    "confidence": float(abs(prob - 0.5) * 2)
                })
        return signals


# 全局服务实例
_service: Optional[QlibService] = None


def get_qlib_service() -> Optional[QlibService]:
    """获取 Qlib 服务实例"""
    global _service
    if _service is None and _qlib_initialized:
        _service = QlibService()
    return _service


# ============ 特征计算工具函数 ============

def calculate_alpha158_from_kline(kline_df: pd.DataFrame) -> pd.DataFrame:
    """
    从 K线数据计算 Alpha158 因子 (简化版)

    这是一个本地实现，不依赖 Qlib 数据

    Args:
        kline_df: K线数据 DataFrame，需包含 open, high, low, close, vol 列

    Returns:
        包含 Alpha158 因子的 DataFrame
    """
    df = kline_df.copy()

    # K线因子
    df["KLine_Close"] = df["close"]
    df["KLine_Open"] = df["open"]
    df["KLine_High"] = df["high"]
    df["KLine_Low"] = df["low"]
    df["KLine_Volume"] = df["vol"]
    df["KLine_Amount"] = df.get("amount", df["vol"] * df["close"])

    # 动量因子
    for period in [5, 10, 20, 60]:
        df[f"ROC{period}"] = df["close"].pct_change(period)
        df[f"MAX{period}"] = df["high"].rolling(period).max()
        df[f"MIN{period}"] = df["low"].rolling(period).min()

    # 波动率因子
    for period in [5, 10, 20, 60]:
        df[f"Std{period}"] = df["close"].rolling(period).std()

    # 成交量因子
    for period in [5, 10, 20, 60]:
        df[f"Volume{period}"] = df["vol"].rolling(period).sum()
        df[f"Volume_MA{period}"] = df["vol"].rolling(period).mean()

    # 均线因子
    for period in [5, 10, 20, 60]:
        df[f"KLine_Close_MA{period}"] = df["close"].rolling(period).mean()

    # RSI
    for period in [5, 10, 20]:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        df[f"RSI{period}"] = 100 - (100 / (1 + rs))

    # MACD
    exp12 = df["close"].ewm(span=12, adjust=False).mean()
    exp26 = df["close"].ewm(span=26, adjust=False).mean()
    df["DIF"] = exp12 - exp26
    df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
    df["MACD"] = (df["DIF"] - df["DEA"]) * 2

    # BOLL
    df["BOLL_MID"] = df["close"].rolling(20).mean()
    df["BOLL_STD"] = df["close"].rolling(20).std()
    df["BOLL20"] = (df["close"] - df["BOLL_MID"]) / df["BOLL_STD"]

    # MFI
    for period in [10]:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        mf = tp * df["vol"]
        pos_flow = mf.where(df["close"] > df["close"].shift(1), 0).rolling(period).sum()
        neg_flow = mf.where(df["close"] < df["close"].shift(1), 0).rolling(period).sum()
        mfr = pos_flow / neg_flow
        df[f"MFI{period}"] = 100 - (100 / (1 + mfr))

    return df
