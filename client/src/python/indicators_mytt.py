#!/usr/bin/env python3
"""
技术指标服务 (MyTT 封装版)
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
"""

import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional

# 导入 MyTT
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
        COUNT, EVERY, EXIST, FILTER,
        BARSLAST, BARSLASTCOUNT, BARSSINCEN,
        LONGCROSS, VALUEWHEN
    )
    MYTT_AVAILABLE = True
except ImportError:
    MYTT_AVAILABLE = False
    print(json.dumps({"success": False, "error": "MyTT not installed"}, ensure_ascii=False))
    sys.exit(1)


class IndicatorCalculator:
    """技术指标计算器"""

    def __init__(self):
        self.mytt_available = MYTT_AVAILABLE

    def calculate(
        self,
        data: List[Dict[str, Any]],
        indicators: List[str],
        params: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, List]:
        """
        计算技术指标

        Args:
            data: K线数据列表
            indicators: 指标名称列表

        Returns:
            {indicator_name: [values]}
        """
        if params is None:
            params = {}

        # 转换为 DataFrame
        df = pd.DataFrame(data)
        close = df["close"].values
        open_ = df["open"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["vol"].values if "vol" in df.columns else np.zeros_like(close)

        results = {}

        for ind in indicators:
            ind_upper = ind.upper()
            ind_params = params.get(ind, {})

            try:
                if ind_upper == "MA":
                    n = ind_params.get("N", 5)
                    results["MA"] = self._to_list(MA(close, n))
                    # 常用均线
                    for m in [10, 20, 60]:
                        results[f"MA{m}"] = self._to_list(MA(close, m))

                elif ind_upper == "EMA":
                    n = ind_params.get("N", 12)
                    results[f"EMA{n}"] = self._to_list(EMA(close, n))

                elif ind_upper == "MACD":
                    s = ind_params.get("SHORT", 12)
                    l = ind_params.get("LONG", 26)
                    m = ind_params.get("M", 9)
                    dif, dea, macd = MACD(close, s, l, m)
                    results["DIF"] = self._to_list(dif)
                    results["DEA"] = self._to_list(dea)
                    results["MACD"] = self._to_list(macd)

                elif ind_upper == "KDJ":
                    n = ind_params.get("N", 9)
                    m1 = ind_params.get("M1", 3)
                    m2 = ind_params.get("M2", 3)
                    k, d, j = KDJ(close, high, low, n, m1, m2)
                    results["K"] = self._to_list(k)
                    results["D"] = self._to_list(d)
                    results["J"] = self._to_list(j)

                elif ind_upper == "RSI":
                    n = ind_params.get("N", 24)
                    results["RSI"] = self._to_list(RSI(close, n))

                elif ind_upper == "BOLL":
                    n = ind_params.get("N", 20)
                    p = ind_params.get("P", 2)
                    upper, middle, lower = BOLL(close, n, p)
                    results["UPPER"] = self._to_list(upper)
                    results["MIDDLE"] = self._to_list(middle)
                    results["LOWER"] = self._to_list(lower)

                elif ind_upper == "WR":
                    n = ind_params.get("N", 10)
                    wr1, wr2 = WR(close, high, low, n)
                    results[f"WR{n}"] = self._to_list(wr1)
                    results[f"WR{2*n}"] = self._to_list(wr2)

                elif ind_upper == "CCI":
                    n = ind_params.get("N", 14)
                    results["CCI"] = self._to_list(CCI(close, high, low, n))

                elif ind_upper == "BIAS":
                    l1 = ind_params.get("L1", 6)
                    results[f"BIAS{l1}"] = self._to_list(BIAS(close, l1)[0])

                elif ind_upper == "DMI":
                    m1 = ind_params.get("M1", 14)
                    m2 = ind_params.get("M2", 6)
                    pdi, mdi, adx, adxr = DMI(close, high, low, m1, m2)
                    results["PDI"] = self._to_list(pdi)
                    results["MDI"] = self._to_list(mdi)
                    results["ADX"] = self._to_list(adx)
                    results["ADXR"] = self._to_list(adxr)

                elif ind_upper == "BBI":
                    results["BBI"] = self._to_list(BBI(close))

                elif ind_upper == "TRIX":
                    m1 = ind_params.get("M1", 12)
                    m2 = ind_params.get("M2", 20)
                    trix, trma = TRIX(close, m1, m2)
                    results["TRIX"] = self._to_list(trix)
                    results["TRMA"] = self._to_list(trma)

                elif ind_upper == "ROC":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    roc, maroc = ROC(close, n, m)
                    results["ROC"] = self._to_list(roc)
                    results["MAROC"] = self._to_list(maroc)

                elif ind_upper == "DPO":
                    m1 = ind_params.get("M1", 20)
                    results["DPO"] = self._to_list(DPO(close, m1)[0])

                elif ind_upper == "EXPMA":
                    results["EXPMA12"] = self._to_list(EXPMA(close, 12)[0])
                    results["EXPMA50"] = self._to_list(EXPMA(close, 50)[0])

                elif ind_upper == "ATR":
                    n = ind_params.get("N", 20)
                    results["ATR"] = self._to_list(ATR(close, high, low, n))

                elif ind_upper == "VR":
                    n = ind_params.get("N", 26)
                    results["VR"] = self._to_list(VR(close, volume, n))

                elif ind_upper == "OBV":
                    results["OBV"] = self._to_list(OBV(close, volume))

                elif ind_upper == "MFI":
                    n = ind_params.get("N", 14)
                    results["MFI"] = self._to_list(MFI(close, high, low, volume, n))

                elif ind_upper == "ASI":
                    m1 = ind_params.get("M1", 26)
                    m2 = ind_params.get("M2", 10)
                    asi, slit = ASI(open_, close, high, low, m1, m2)
                    results["ASI"] = self._to_list(asi)
                    results["SLIT"] = self._to_list(slit)

                elif ind_upper == "BRAR":
                    m1 = ind_params.get("M1", 26)
                    ar, br = BRAR(open_, close, high, low, m1)
                    results["AR"] = self._to_list(ar)
                    results["BR"] = self._to_list(br)

                elif ind_upper == "PSY":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    psy, psyma = PSY(close, n, m)
                    results["PSY"] = self._to_list(psy)
                    results["PSYMA"] = self._to_list(psyma)

                elif ind_upper == "MTM":
                    n = ind_params.get("N", 12)
                    m = ind_params.get("M", 6)
                    mtm, mtmm = MTM(close, n, m)
                    results["MTM"] = self._to_list(mtm)
                    results["MTMMA"] = self._to_list(mtmm)

                elif ind_upper == "HHV":
                    n = ind_params.get("N", 20)
                    results[f"HHV{n}"] = self._to_list(HHV(close, n))

                elif ind_upper == "LLV":
                    n = ind_params.get("N", 20)
                    results[f"LLV{n}"] = self._to_list(LLV(close, n))

            except Exception as e:
                print(json.dumps({"success": False, "error": f"计算指标 {ind} 失败: {e}"}, ensure_ascii=False))
                sys.exit(1)

        return results

    def _to_list(self, arr) -> List:
        """转换为 Python 列表，处理 NaN"""
        result = []
        for v in arr:
            if isinstance(v, (int, float)):
                if np.isnan(v):
                    result.append(None)
                else:
                    result.append(float(v))
            else:
                result.append(v)
        return result

    def detect_signals(
        self,
        data: List[Dict[str, Any]],
        strategy_type: str = "ma_cross"
    ) -> List[Dict[str, Any]]:
        """
        检测交易信号

        Args:
            data: K线数据
            strategy_type: 策略类型

        Returns:
            [{date, signal, price, reason}, ...]
        """
        df = pd.DataFrame(data)
        close = df["close"].values
        open_ = df["open"].values
        high = df["high"].values
        low = df["low"].values

        signals = []

        if strategy_type == "ma_cross":
            ma5 = MA(close, 5)
            ma20 = MA(close, 20)

            for i in range(1, len(close)):
                if np.isnan(ma5[i]) or np.isnan(ma20[i]):
                    continue
                # 金叉
                if ma5[i-1] <= ma20[i-1] and ma5[i] > ma20[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": "MA5上穿MA20"
                    })
                # 死叉
                elif ma5[i-1] >= ma20[i-1] and ma5[i] < ma20[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": "MA5下穿MA20"
                    })

        elif strategy_type == "kdj_cross":
            k, d, j = KDJ(close, high, low)

            for i in range(1, len(close)):
                if np.isnan(k[i]) or np.isnan(d[i]):
                    continue
                # 金叉
                if k[i-1] <= d[i-1] and k[i] > d[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": "KDJ金叉"
                    })
                # 死叉
                elif k[i-1] >= d[i-1] and k[i] < d[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": "KDJ死叉"
                    })

        elif strategy_type == "macd_cross":
            dif, dea, _ = MACD(close)

            for i in range(1, len(close)):
                if np.isnan(dif[i]) or np.isnan(dea[i]):
                    continue
                # 金叉
                if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": "MACD金叉"
                    })
                # 死叉
                elif dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": "MACD死叉"
                    })

        elif strategy_type == "rsi_signal":
            rsi = RSI(close)

            for i in range(1, len(close)):
                if np.isnan(rsi[i]):
                    continue
                # RSI 超卖反弹
                if rsi[i-1] <= 30 and rsi[i] > 30:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": f"RSI超卖反弹({rsi[i]:.1f})"
                    })
                # RSI 超买回落
                elif rsi[i-1] >= 70 and rsi[i] < 70:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": f"RSI超买回落({rsi[i]:.1f})"
                    })

        elif strategy_type == "bollinger":
            upper, middle, lower = BOLL(close)

            for i in range(len(close)):
                if np.isnan(upper[i]):
                    continue
                # 价格突破上轨
                if close[i] > upper[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": "布林带上轨突破"
                    })
                # 价格突破下轨
                elif close[i] < lower[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": "布林带下轨突破"
                    })

        elif strategy_type == "dmi_signal":
            pdi, mdi, adx, adxr = DMI(close, high, low)

            for i in range(1, len(close)):
                if np.isnan(adx[i]):
                    continue
                # ADX 上升趋势确认
                if adx[i] > 25 and pdi[i] > mdi[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "BUY",
                        "price": float(close[i]),
                        "reason": f"DMI多头(ADX={adx[i]:.1f})"
                    })
                elif adx[i] > 25 and mdi[i] > pdi[i]:
                    signals.append({
                        "date": data[i]["trade_date"],
                        "signal": "SELL",
                        "price": float(close[i]),
                        "reason": f"DMI空头(ADX={adx[i]:.1f})"
                    })

        return signals


def run_command(cmd: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行命令"""
    calc = IndicatorCalculator()

    if cmd == "calculate":
        data = params.get("data", [])
        indicators = params.get("indicators", [])
        ind_params = params.get("params", {})

        results = calc.calculate(data, indicators, ind_params)
        return {"success": True, "data": results}

    elif cmd == "signals":
        data = params.get("data", [])
        strategy_type = params.get("strategy_type", "ma_cross")

        signals = calc.detect_signals(data, strategy_type)
        return {"success": True, "data": {"signals": signals, "total": len(signals)}}

    else:
        return {"success": False, "error": f"Unknown command: {cmd}"}


if __name__ == "__main__":
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
