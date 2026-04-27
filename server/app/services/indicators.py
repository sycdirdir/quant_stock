"""
技术指标服务
基于 MyTT 库实现完整的技术指标计算
参考: https://github.com/mpquant/MyTT

支持指标：
- 均线类: MA, EMA, SMA, WMA, DMA, BBI
- 超买超卖: KDJ, RSI, WR(威廉), CCI, BIAS
- 趋势类: MACD, DMI, TRIX, ROC, DPO, EXPMA
- 通道类: BOLL, ATR, TAQ(唐安奇), KTN(肯特纳)
- 能量类: VR, EMV, OBV, MFI, ASI
- 情绪类: BRAR, PSY, MASS
- 动量类: MTM
- 其他: HHV, LLV, STD, SUM, DIFF
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# 尝试导入 MyTT
try:
    from MyTT import (
        MA, EMA, SMA, WMA, DMA, BBI,
        KDJ, RSI, WR, CCI, BIAS,
        MACD, DMI, TRIX, ROC, DPO, EXPMA,
        BOLL, ATR, TAQ, KTN,
        VR, EMV, OBV, MFI, ASI,
        BRAR, PSY, MASS, MTM,
        HHV, LLV, STD, SUM, DIFF,
        REF, CROSS, IF, MAX, MIN, ABS,
        STD as STD_FUNC, SUM as SUM_FUNC
    )
    MYTT_AVAILABLE = True
except ImportError:
    logger.warning("MyTT not installed, using pure Python implementation")
    MYTT_AVAILABLE = False


class IndicatorService:
    """技术指标服务"""

    def __init__(self):
        self.mytt_available = MYTT_AVAILABLE

    def calculate(
        self,
        data: pd.DataFrame,
        indicators: List[str],
        params: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, np.ndarray]:
        """
        计算技术指标

        Args:
            data: K线数据 DataFrame, 必须包含 open, high, low, close, volume 列
            indicators: 指标名称列表，如 ["MA", "KDJ", "MACD"]
            params: 指标参数字典，如 {"MA": {"N": 5}, "KDJ": {"N": 9}}

        Returns:
            {indicator_name: result_array}
        """
        if params is None:
            params = {}

        results = {}
        close = data["close"].values
        open_ = data["open"].values
        high = data["high"].values
        low = data["low"].values
        volume = data["volume"].values if "volume" in data.columns else np.zeros_like(close)

        for ind in indicators:
            ind_upper = ind.upper()
            ind_params = params.get(ind, {})

            try:
                if ind_upper == "MA":
                    n = ind_params.get("N", 5)
                    results["MA"] = MA(close, n)
                    # 同时计算常用均线
                    for m in [10, 20, 60]:
                        if m != n:
                            results[f"MA{m}"] = MA(close, m)

                elif ind_upper == "EMA":
                    n = ind_params.get("N", 12)
                    results[f"EMA{n}"] = EMA(close, n)

                elif ind_upper == "MACD":
                    s = ind_params.get("SHORT", 12)
                    l = ind_params.get("LONG", 26)
                    m = ind_params.get("M", 9)
                    dif, dea, macd = MACD(close, s, l, m)
                    results["DIF"] = dif
                    results["DEA"] = dea
                    results["MACD"] = macd

                elif ind_upper == "KDJ":
                    n = ind_params.get("N", 9)
                    m1 = ind_params.get("M1", 3)
                    m2 = ind_params.get("M2", 3)
                    k, d, j = KDJ(close, high, low, n, m1, m2)
                    results["K"] = k
                    results["D"] = d
                    results["J"] = j

                elif ind_upper == "RSI":
                    n = ind_params.get("N", 24)
                    results["RSI"] = RSI(close, n)

                elif ind_upper == "BOLL":
                    n = ind_params.get("N", 20)
                    p = ind_params.get("P", 2)
                    upper, middle, lower = BOLL(close, n, p)
                    results["UPPER"] = upper
                    results["MIDDLE"] = middle
                    results["LOWER"] = lower

                elif ind_upper == "WR":
                    n = ind_params.get("N", 10)
                    wr1, wr2 = WR(close, high, low, n)
                    results[f"WR{n}"] = wr1
                    results[f"WR{2*n}"] = wr2

                elif ind_upper == "CCI":
                    n = ind_params.get("N", 14)
                    results["CCI"] = CCI(close, high, low, n)

                elif ind_upper == "BIAS":
                    l1 = ind_params.get("L1", 6)
                    results[f"BIAS{l1}"] = BIAS(close, l1)[0]

                elif ind_upper == "DMI":
                    m1 = ind_params.get("M1", 14)
                    m2 = ind_params.get("M2", 6)
                    pdi, mdi, adx, adxr = DMI(close, high, low, m1, m2)
                    results["PDI"] = pdi
                    results["MDI"] = mdi
                    results["ADX"] = adx
                    results["ADXR"] = adxr

                elif ind_upper == "BBI":
                    results["BBI"] = BBI(close)

                elif ind_upper == "TRIX":
                    m1 = ind_params.get("M1", 12)
                    m2 = ind_params.get("M2", 20)
                    trix, trma = TRIX(close, m1, m2)
                    results["TRIX"] = trix
                    results["TRMA"] = trma

                elif ind_upper == "ROC":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    roc, maroc = ROC(close, n, m)
                    results["ROC"] = roc
                    results["MAROC"] = maroc

                elif ind_upper == "DPO":
                    m1 = ind_params.get("M1", 20)
                    results["DPO"] = DPO(close, m1)[0]

                elif ind_upper == "EXPMA":
                    results["EXPMA12"] = EXPMA(close, 12)[0]
                    results["EXPMA50"] = EXPMA(close, 50)[0]

                elif ind_upper == "ATR":
                    n = ind_params.get("N", 20)
                    results["ATR"] = ATR(close, high, low, n)

                elif ind_upper == "TAQ":
                    n = ind_params.get("N", 20)
                    up, mid, down = TAQ(high, low, n)
                    results["TAQ_UP"] = up
                    results["TAQ_MID"] = mid
                    results["TAQ_DOWN"] = down

                elif ind_upper == "KTN":
                    n = ind_params.get("N", 20)
                    m = ind_params.get("M", 10)
                    upper, middle, lower = KTN(close, high, low, n, m)
                    results["KTN_UPPER"] = upper
                    results["KTN_MIDDLE"] = middle
                    results["KTN_LOWER"] = lower

                elif ind_upper == "VR":
                    n = ind_params.get("N", 26)
                    results["VR"] = VR(close, volume, n)

                elif ind_upper == "EMV":
                    n = ind_params.get("N", 14)
                    emv, maemv = EMV(high, low, volume, n)
                    results["EMV"] = emv
                    results["MAEMV"] = maemv

                elif ind_upper == "OBV":
                    results["OBV"] = OBV(close, volume)

                elif ind_upper == "MFI":
                    n = ind_params.get("N", 14)
                    results["MFI"] = MFI(close, high, low, volume, n)

                elif ind_upper == "ASI":
                    m1 = ind_params.get("M1", 26)
                    m2 = ind_params.get("M2", 10)
                    asi, slit = ASI(open_, close, high, low, m1, m2)
                    results["ASI"] = asi
                    results["SLIT"] = slit

                elif ind_upper == "BRAR":
                    m1 = ind_params.get("M1", 26)
                    ar, br = BRAR(open_, close, high, low, m1)
                    results["AR"] = ar
                    results["BR"] = br

                elif ind_upper == "PSY":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    psy, psyma = PSY(close, n, m)
                    results["PSY"] = psy
                    results["PSYMA"] = psyma

                elif ind_upper == "MASS":
                    results["MASS"] = MASS(high, low)[0]

                elif ind_upper == "MTM":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    mtm, mtmm = MTM(close, n, m)
                    results["MTM"] = mtm
                    results["MTMMA"] = mtmm

                elif ind_upper == "HHV":
                    n = ind_params.get("N", 20)
                    results[f"HHV{n}"] = HHV(close, n)

                elif ind_upper == "LLV":
                    n = ind_params.get("N", 20)
                    results[f"LLV{n}"] = LLV(close, n)

                elif ind_upper == "STD":
                    n = ind_params.get("N", 20)
                    results[f"STD{n}"] = STD(close, n)

                else:
                    logger.warning(f"Unknown indicator: {ind}")

            except Exception as e:
                logger.error(f"计算指标 {ind} 失败: {e}")

        return results

    def get_standard_indicators(self, data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        计算标准指标集 (常用指标组合)

        Args:
            data: K线数据 DataFrame

        Returns:
            包含所有标准指标的字典
        """
        indicators = ["MA", "MACD", "KDJ", "RSI", "BOLL", "WR", "CCI", "DMI"]
        return self.calculate(data, indicators)

    def detect_signals(
        self,
        data: pd.DataFrame,
        strategy_type: str = "ma_cross"
    ) -> List[Dict[str, Any]]:
        """
        检测交易信号

        Args:
            data: K线数据
            strategy_type: 策略类型:
                - "ma_cross": 均线交叉
                - "kdj_cross": KDJ金叉死叉
                - "macd_cross": MACD金叉死叉
                - "rsi_signal": RSI超买超卖
                - "bollinger": 布林带突破
                - "dmi_signal": DMI趋势信号

        Returns:
            [{date, signal, price, reason}, ...]
        """
        close = data["close"].values
        signals = []

        if strategy_type == "ma_cross":
            ma5 = MA(close, 5)
            ma20 = MA(close, 20)

            for i in range(1, len(close)):
                if not np.isnan(ma5[i]) and not np.isnan(ma20[i]):
                    # 金叉
                    if ma5[i-1] <= ma20[i-1] and ma5[i] > ma20[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": "MA5上穿MA20"
                        })
                    # 死叉
                    elif ma5[i-1] >= ma20[i-1] and ma5[i] < ma20[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": "MA5下穿MA20"
                        })

        elif strategy_type == "kdj_cross":
            k, d, j = KDJ(close, data["high"].values, data["low"].values)

            for i in range(1, len(close)):
                if not np.isnan(k[i]) and not np.isnan(d[i]):
                    # 金叉
                    if k[i-1] <= d[i-1] and k[i] > d[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": "KDJ金叉"
                        })
                    # 死叉
                    elif k[i-1] >= d[i-1] and k[i] < d[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": "KDJ死叉"
                        })

        elif strategy_type == "macd_cross":
            dif, dea, _ = MACD(close)

            for i in range(1, len(close)):
                if not np.isnan(dif[i]) and not np.isnan(dea[i]):
                    # 金叉
                    if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": "MACD金叉"
                        })
                    # 死叉
                    elif dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": "MACD死叉"
                        })

        elif strategy_type == "rsi_signal":
            rsi = RSI(close)

            for i in range(1, len(close)):
                if not np.isnan(rsi[i]):
                    # RSI 超卖反弹
                    if rsi[i-1] <= 30 and rsi[i] > 30:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": f"RSI超卖反弹({rsi[i]:.1f})"
                        })
                    # RSI 超买回落
                    elif rsi[i-1] >= 70 and rsi[i] < 70:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": f"RSI超买回落({rsi[i]:.1f})"
                        })

        elif strategy_type == "bollinger":
            upper, middle, lower = BOLL(close)

            for i in range(len(close)):
                if not np.isnan(upper[i]):
                    # 价格突破上轨
                    if close[i] > upper[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": "布林带上轨突破"
                        })
                    # 价格突破下轨
                    elif close[i] < lower[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": "布林带下轨突破"
                        })

        elif strategy_type == "dmi_signal":
            pdi, mdi, adx, adxr = DMI(close, data["high"].values, data["low"].values)

            for i in range(1, len(close)):
                if not np.isnan(adx[i]):
                    # ADX 上升趋势确认
                    if adx[i] > 25 and pdi[i] > mdi[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "BUY",
                            "price": close[i],
                            "reason": f"DMI多头(ADX={adx[i]:.1f})"
                        })
                    elif adx[i] > 25 and mdi[i] > pdi[i]:
                        signals.append({
                            "date": data.index[i] if hasattr(data.index, '__getitem__') else data.iloc[i]["trade_date"],
                            "signal": "SELL",
                            "price": close[i],
                            "reason": f"DMI空头(ADX={adx[i]:.1f})"
                        })

        return signals


# 全局服务实例
_indicator_service: Optional[IndicatorService] = None


def get_indicator_service() -> IndicatorService:
    """获取指标服务实例"""
    global _indicator_service
    if _indicator_service is None:
        _indicator_service = IndicatorService()
    return _indicator_service
