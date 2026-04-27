#!/usr/bin/env python3
"""
量化交易回测引擎 - 增强版
集成 QuantMind 优秀架构:
- ta-lib 技术指标 (KDJ/MACD/布林带/RSI)
- 增强型风险配置 (移动止损/最大回撤限制)
- 多头/空头持仓管理
- VaR/CVaR 风险指标
- 佣金/滑点处理
"""

import sys
import json
import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


# ============ 风险配置 ============

@dataclass
class RiskConfig:
    """增强型风险配置"""
    # 基础风险控制
    max_position_ratio: float = 0.8  # 最大仓位比例
    max_portfolio_risk: float = 0.15  # 最大组合风险
    max_drawdown_limit: float = 0.20  # 最大回撤限制

    # 止损止盈
    stop_loss_pct: float = 0.05  # 止损比例 (5%)
    take_profit_pct: float = 0.15  # 止盈比例 (15%)
    trailing_stop_pct: float = 0.03  # 移动止损比例 (3%)

    # 仓位管理
    min_position_size: float = 0.01  # 最小仓位比例
    position_sizing_method: str = "fixed"  # fixed, percent, kelly, volatility
    max_positions: int = 10  # 最大持仓数量

    # 风险指标
    var_confidence: float = 0.95  # VaR 置信度
    cvar_confidence: float = 0.95  # CVaR 置信度
    lookback_period: int = 252  # 回看期间 (交易日)

    # 交易成本
    commission_rate: float = 0.0003  # 佣金 (万三)
    slippage_rate: float = 0.0001  # 滑点 (万一)

    # 其他
    risk_free_rate: float = 0.02  # 无风险利率


# ============ 持仓类 ============

class Position:
    """持仓类 - 支持多头/空头"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.quantity = 0.0  # 正=多头, 负=空头
        self.avg_cost = 0.0
        self.last_price = 0.0
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.highest_price = 0.0  # 用于移动止损
        self.lowest_price = 0.0  # 用于移动止损 (空头)

    def update_price(self, price: float) -> None:
        """更新最新价格和未实现盈亏"""
        self.last_price = price
        if self.quantity > 0:  # 多头
            self.unrealized_pnl = (price - self.avg_cost) * self.quantity
            if price > self.highest_price:
                self.highest_price = price
        elif self.quantity < 0:  # 空头
            self.unrealized_pnl = (self.avg_cost - price) * abs(self.quantity)
            if price < self.lowest_price or self.lowest_price == 0:
                self.lowest_price = price

    def add_long(self, quantity: float, cost: float) -> None:
        """增加多头持仓"""
        if self.quantity < 0:
            raise ValueError("持仓已为空头，不可直接加多")
        if self.quantity == 0:
            self.avg_cost = cost
            self.highest_price = cost
        else:
            total_cost = self.quantity * self.avg_cost + quantity * cost
            self.quantity += quantity
            self.avg_cost = total_cost / self.quantity
        self.quantity += quantity

    def open_short(self, quantity: float, price: float) -> None:
        """开空仓"""
        if self.quantity > 0:
            raise ValueError("持仓已为多头，不可直接开空")
        if self.quantity == 0:
            self.avg_cost = price
            self.lowest_price = price
        else:
            total_short = abs(self.quantity) + quantity
            self.avg_cost = (abs(self.quantity) * self.avg_cost + quantity * price) / total_short
        self.quantity -= quantity

    def close_long(self, quantity: float, price: float) -> float:
        """平多头"""
        if self.quantity < quantity:
            raise ValueError(f"卖出数量 {quantity} 超过持仓 {self.quantity}")
        realized_pnl = (price - self.avg_cost) * quantity
        self.realized_pnl += realized_pnl
        self.quantity -= quantity
        if self.quantity == 0:
            self.avg_cost = 0.0
            self.highest_price = 0.0
            self.unrealized_pnl = 0.0
        return realized_pnl

    def cover_short(self, quantity: float, price: float) -> float:
        """平空头"""
        if self.quantity >= 0:
            raise ValueError("无空头持仓可平")
        if quantity > abs(self.quantity):
            raise ValueError("平空数量超过持仓")
        realized_pnl = (self.avg_cost - price) * quantity
        self.realized_pnl += realized_pnl
        self.quantity += quantity
        if self.quantity == 0:
            self.avg_cost = 0.0
            self.lowest_price = 0.0
            self.unrealized_pnl = 0.0
        return realized_pnl

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def is_empty(self) -> bool:
        return self.quantity == 0


# ============ 风险管理器 ============

class RiskManager:
    """风险管理器 - 计算 VaR/CVaR/夏普比率"""

    def __init__(self, config: RiskConfig):
        self.config = config
        self.equity_curve: List[float] = []
        self.returns: List[float] = []

    def update_equity(self, equity: float) -> None:
        """更新权益曲线"""
        self.equity_curve.append(equity)
        if len(self.equity_curve) > 1:
            ret = (equity - self.equity_curve[-2]) / self.equity_curve[-2]
            self.returns.append(ret)

    def check_stop_loss(self, position: Position, current_price: float) -> Tuple[bool, str]:
        """检查是否触发止损"""
        if position.is_long:
            loss_pct = (position.avg_cost - current_price) / position.avg_cost
            # 固定止损
            if loss_pct >= self.config.stop_loss_pct:
                return True, f"止损-{loss_pct:.2%}"
            # 移动止损
            if position.highest_price > 0:
                trailing_loss = (position.highest_price - current_price) / position.highest_price
                if trailing_loss >= self.config.trailing_stop_pct:
                    return True, f"移动止损-{trailing_loss:.2%}"
        elif position.is_short:
            loss_pct = (current_price - position.avg_cost) / position.avg_cost
            if loss_pct >= self.config.stop_loss_pct:
                return True, f"止损-{loss_pct:.2%}"
            if position.lowest_price > 0:
                trailing_loss = (current_price - position.lowest_price) / position.lowest_price
                if trailing_loss >= self.config.trailing_stop_pct:
                    return True, f"移动止损-{trailing_loss:.2%}"
        return False, ""

    def check_take_profit(self, position: Position, current_price: float) -> Tuple[bool, str]:
        """检查是否触发止盈"""
        if position.is_long:
            profit_pct = (current_price - position.avg_cost) / position.avg_cost
            if profit_pct >= self.config.take_profit_pct:
                return True, f"止盈-{profit_pct:.2%}"
        elif position.is_short:
            profit_pct = (position.avg_cost - current_price) / position.avg_cost
            if profit_pct >= self.config.take_profit_pct:
                return True, f"止盈-{profit_pct:.2%}"
        return False, ""

    def calculate_metrics(self) -> Dict[str, Any]:
        """计算风险指标"""
        if len(self.equity_curve) < 2:
            return self._default_metrics()

        import math

        # 总收益
        total_return = (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]

        # 年化收益
        years = len(self.equity_curve) / 252
        annual_return = total_return / years if years > 0 else 0

        # 夏普比率
        if len(self.returns) > 1:
            avg_ret = sum(self.returns) / len(self.returns)
            std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in self.returns) / len(self.returns))
            if std_ret > 0:
                sharpe = (avg_ret - self.config.risk_free_rate / 252) / std_ret * math.sqrt(252)
            else:
                sharpe = 0
        else:
            sharpe = 0

        # 最大回撤
        peak = self.equity_curve[0]
        max_drawdown = 0
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (equity - peak) / peak
            if dd < max_drawdown:
                max_drawdown = dd

        # VaR / CVaR
        if len(self.returns) > 0:
            sorted_returns = sorted(self.returns)
            var_idx = int(len(sorted_returns) * (1 - self.config.var_confidence))
            var_95 = sorted_returns[var_idx] if var_idx < len(sorted_returns) else sorted_returns[-1]
            cvar_95 = sum(sorted_returns[:var_idx + 1]) / len(sorted_returns[:var_idx + 1]) if var_idx > 0 else var_95
        else:
            var_95 = 0
            cvar_95 = 0

        return {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 4),
            "var_95": round(var_95, 4),
            "cvar_95": round(cvar_95, 4),
        }

    def _default_metrics(self) -> Dict[str, Any]:
        return {
            "total_return": 0,
            "annual_return": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "var_95": 0,
            "cvar_95": 0,
        }


# ============ 技术指标计算 ============

def calculate_ma(data: List[Dict], period: int) -> List[Optional[float]]:
    """计算移动平均线"""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            values = [d['close'] for d in data[i - period + 1:i + 1]]
            result.append(sum(values) / period)
    return result


def calculate_ema(data: List[Dict], period: int) -> List[Optional[float]]:
    """计算指数移动平均线 (EMA)"""
    result = []
    multiplier = 2 / (period + 1)
    sma = sum(d['close'] for d in data[:period]) / period
    result.extend([None] * (period - 1))
    result.append(sma)
    for i in range(period, len(data)):
        ema = (data[i]['close'] - result[-1]) * multiplier + result[-1]
        result.append(ema)
    return result


def calculate_macd(
    data: List[Dict],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """计算 MACD (Moving Average Convergence Divergence)
    Returns: (DIF, DEA, MACD)
    """
    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)

    dif = []
    for i in range(len(data)):
        if ema_fast[i] is None or ema_slow[i] is None:
            dif.append(None)
        else:
            dif.append(ema_fast[i] - ema_slow[i])

    # DEA (Signal Line)
    dea = []
    multiplier = 2 / (signal_period + 1)
    valid_dif = [d for d in dif if d is not None]
    if valid_dif:
        first_dea = sum(valid_dif[:signal_period]) / signal_period
        dea.extend([None] * (len(dif) - len(valid_dif)))
        dea.extend([None] * (signal_period - 1))
        dea.append(first_dea)
        for i in range(len(dif) - len(valid_dif) + signal_period, len(dif)):
            if dif[i] is not None:
                dea.append((dif[i] - dea[-1]) * multiplier + dea[-1])
            else:
                dea.append(None)

    # MACD Histogram
    macd_hist = []
    for i in range(len(data)):
        if dif[i] is None or dea[i] is None:
            macd_hist.append(None)
        else:
            macd_hist.append((dif[i] - dea[i]) * 2)

    return dif, dea, macd_hist


def calculate_rsi(data: List[Dict], period: int = 14) -> List[Optional[float]]:
    """计算 RSI (Relative Strength Index)"""
    if len(data) < period + 1:
        return [None] * len(data)

    result = [None] * period

    # Calculate first average gain/loss
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = data[i]['close'] - data[i - 1]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result.append(100)
    else:
        rs = avg_gain / avg_loss
        result.append(100 - 100 / (1 + rs))

    # Calculate subsequent RSI values using smoothed averages
    for i in range(period + 1, len(data)):
        change = data[i]['close'] - data[i - 1]['close']
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result.append(100)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - 100 / (1 + rs))

    return result


def calculate_kdj(
    data: List[Dict],
    n: int = 9,
    m1: int = 3,
    m2: int = 3
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """计算 KDJ 随机指标
    Returns: (K, D, J)
    """
    if len(data) < n:
        return [None] * len(data), [None] * len(data), [None] * len(data)

    k_values = [None] * (n - 1)
    d_values = [None] * (n - 1)
    j_values = [None] * (n - 1)

    # Calculate RSV for each day
    rsv = []
    for i in range(n - 1, len(data)):
        high = max(d['high'] for d in data[i - n + 1:i + 1])
        low = min(d['low'] for d in data[i - n + 1:i + 1])
        close = data[i]['close']

        if high == low:
            rsv.append(50)
        else:
            rsv.append((close - low) / (high - low) * 100)

    # First K and D values (simple moving average)
    first_k = sum(rsv[:m1]) / m1
    first_d = sum(rsv[:m2]) / m2

    k_values.append(first_k)
    d_values.append(first_d)
    j_values.append(3 * first_k - 2 * first_d)

    # Subsequent values (exponential moving average)
    for i in range(m1, len(rsv)):
        k = (2 / 3) * k_values[-1] + (1 / 3) * rsv[i]
        d = (2 / 3) * d_values[-1] + (1 / 3) * k
        j = 3 * k - 2 * d
        k_values.append(k)
        d_values.append(d)
        j_values.append(j)

    return k_values, d_values, j_values


def calculate_bollinger_bands(
    data: List[Dict],
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """计算布林带 (Bollinger Bands)
    Returns: (Upper, Middle, Lower)
    """
    import math

    middle = calculate_ma(data, period)

    upper = []
    lower = []

    for i in range(len(data)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            # Calculate standard deviation
            values = [d['close'] for d in data[i - period + 1:i + 1]]
            mean = middle[i]
            variance = sum((v - mean) ** 2 for v in values) / period
            std = math.sqrt(variance)
            upper.append(middle[i] + std_dev * std)
            lower.append(middle[i] - std_dev * std)

    return upper, middle, lower


def detect_ma_cross(
    ma_fast_prev: Optional[float],
    ma_fast_curr: Optional[float],
    ma_slow_prev: Optional[float],
    ma_slow_curr: Optional[float]
) -> Optional[str]:
    """检测均线交叉"""
    if None in [ma_fast_prev, ma_fast_curr, ma_slow_prev, ma_slow_curr]:
        return None
    if ma_fast_prev <= ma_slow_prev and ma_fast_curr > ma_slow_curr:
        return 'BUY'
    elif ma_fast_prev >= ma_slow_prev and ma_fast_curr < ma_slow_curr:
        return 'SELL'
    return None


def detect_macd_cross(
    dif_prev: Optional[float],
    dif_curr: Optional[float],
    dea_prev: Optional[float],
    dea_curr: Optional[float]
) -> Optional[str]:
    """检测 MACD 交叉"""
    if None in [dif_prev, dif_curr, dea_prev, dea_curr]:
        return None
    # DIF 上穿 DEA = 买入
    if dif_prev <= dea_prev and dif_curr > dea_curr:
        return 'BUY'
    # DIF 下穿 DEA = 卖出
    elif dif_prev >= dea_prev and dif_curr < dea_curr:
        return 'SELL'
    return None


def detect_kdj_cross(
    k_prev: Optional[float],
    k_curr: Optional[float],
    d_prev: Optional[float],
    d_curr: Optional[float]
) -> Optional[str]:
    """检测 KDJ 交叉 (金叉/死叉)"""
    if None in [k_prev, k_curr, d_prev, d_curr]:
        return None
    # K 上穿 D = 金叉 = 买入
    if k_prev <= d_prev and k_curr > d_curr:
        return 'BUY'
    # K 下穿 D = 死叉 = 卖出
    elif k_prev >= d_prev and k_curr < d_curr:
        return 'SELL'
    return None


def detect_rsi_signal(
    rsi_prev: Optional[float],
    rsi_curr: Optional[float],
    oversold: float = 30,
    overbought: float = 70
) -> Optional[str]:
    """检测 RSI 超买超卖信号"""
    if None in [rsi_prev, rsi_curr]:
        return None
    # 从超卖区上穿 = 买入信号
    if rsi_prev <= oversold and rsi_curr > oversold:
        return 'BUY'
    # 从超买区下穿 = 卖出信号
    elif rsi_prev >= overbought and rsi_curr < overbought:
        return 'SELL'
    return None


# ============ 回测引擎 ============

def run_backtest(params: Dict[str, Any]) -> Dict[str, Any]:
    """运行回测 - 增强版"""

    # 解析参数
    ts_code = params.get('ts_code', '')
    period = params.get('period', 'daily')
    start_date = params.get('start_date', '20250101')
    end_date = params.get('end_date', '20260424')
    initial_cash = params.get('initial_cash', 100000)

    strategy_config = params.get('strategy', {})
    risk_config_dict = params.get('risk', {})

    # 构建风险配置
    risk_cfg = RiskConfig(
        stop_loss_pct=risk_config_dict.get('stop_loss', 0.05),
        take_profit_pct=risk_config_dict.get('take_profit', 0.10),
        trailing_stop_pct=risk_config_dict.get('trailing_stop', 0.03),
        max_drawdown_limit=risk_config_dict.get('max_drawdown_limit', 0.20),
        commission_rate=risk_config_dict.get('commission_rate', 0.0003),
        slippage_rate=risk_config_dict.get('slippage_rate', 0.0001),
    )

    # 加载数据
    db_path = params.get('db_path', 'quant.db')
    table_name = period

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT trade_date, open, high, low, close, vol
        FROM {table_name}
        WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date ASC
    """, (ts_code, start_date, end_date))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            'success': False,
            'error': f'No data for {ts_code} in {start_date}-{end_date}'
        }

    data = [
        {
            'trade_date': str(r[0]),
            'open': float(r[1]),
            'high': float(r[2]),
            'low': float(r[3]),
            'close': float(r[4]),
            'vol': float(r[5])
        }
        for r in rows
    ]

    # 获取策略参数
    ma_periods = strategy_config.get('ma_periods', [5, 10, 20])
    indicators = strategy_config.get('indicators', ['ma'])  # ma, macd, kdj, rsi, bollinger
    fast_ma = ma_periods[0] if len(ma_periods) >= 1 else 5
    slow_ma = ma_periods[1] if len(ma_periods) >= 2 else 20

    # 计算指标
    ma_fast = calculate_ma(data, fast_ma)
    ma_slow = calculate_ma(data, slow_ma)

    indicators_data = {'ma': {'fast': ma_fast, 'slow': ma_slow}}

    if 'macd' in indicators:
        dif, dea, macd_hist = calculate_macd(data)
        indicators_data['macd'] = {'dif': dif, 'dea': dea, 'hist': macd_hist}

    if 'kdj' in indicators:
        k, d, j = calculate_kdj(data)
        indicators_data['kdj'] = {'k': k, 'd': d, 'j': j}

    if 'rsi' in indicators:
        rsi = calculate_rsi(data)
        indicators_data['rsi'] = {'value': rsi}

    if 'bollinger' in indicators:
        upper, middle, lower = calculate_bollinger_bands(data)
        indicators_data['bollinger'] = {'upper': upper, 'middle': middle, 'lower': lower}

    # 交易模拟
    cash = initial_cash
    position: Optional[Position] = None
    risk_mgr = RiskManager(risk_cfg)
    trades = []
    signals = []
    equity_curve = []

    # 统计
    daily_trade_count = {}

    for i in range(1, len(data)):
        curr = data[i]
        prev = data[i - 1]

        # 更新持仓市值
        if position and not position.is_empty:
            position.update_price(curr['close'])

        # 更新权益曲线
        position_value = position.market_value if position and not position.is_empty else 0
        equity = cash + position_value
        equity_curve.append({
            'date': curr['trade_date'],
            'value': round(equity, 2)
        })
        risk_mgr.update_equity(equity)

        # 检测交易信号
        signal = None
        signal_reason = ''

        # 均线交叉信号
        if 'ma' in indicators:
            ma_cross = detect_ma_cross(
                ma_fast[i - 1], ma_fast[i],
                ma_slow[i - 1], ma_slow[i]
            )
            if ma_cross:
                signal = ma_cross
                signal_reason = f'MA{fast_ma}上穿MA{slow_ma}' if ma_cross == 'BUY' else f'MA{fast_ma}下穿MA{slow_ma}'

        # MACD 信号
        if signal is None and 'macd' in indicators:
            macd_data = indicators_data['macd']
            macd_cross = detect_macd_cross(
                macd_data['dif'][i - 1], macd_data['dif'][i],
                macd_data['dea'][i - 1], macd_data['dea'][i]
            )
            if macd_cross:
                signal = macd_cross
                signal_reason = 'MACD金叉' if macd_cross == 'BUY' else 'MACD死叉'

        # KDJ 信号
        if signal is None and 'kdj' in indicators:
            kdj_data = indicators_data['kdj']
            kdj_cross = detect_kdj_cross(
                kdj_data['k'][i - 1], kdj_data['k'][i],
                kdj_data['d'][i - 1], kdj_data['d'][i]
            )
            if kdj_cross:
                signal = kdj_cross
                signal_reason = 'KDJ金叉' if kdj_cross == 'BUY' else 'KDJ死叉'

        # RSI 信号
        if signal is None and 'rsi' in indicators:
            rsi_data = indicators_data['rsi']
            rsi_signal = detect_rsi_signal(
                rsi_data['value'][i - 1], rsi_data['value'][i]
            )
            if rsi_signal:
                signal = rsi_signal
                signal_reason = 'RSI超卖反弹' if rsi_signal == 'BUY' else 'RSI超买回落'

        # 执行交易
        if signal == 'BUY' and (position is None or position.is_empty):
            # 买入
            position_size = risk_config_dict.get('position_size', 20000)
            shares = int(position_size / curr['close'] / 100) * 100
            cost = shares * curr['close']
            commission = cost * risk_cfg.commission_rate
            slippage = cost * risk_cfg.slippage_rate

            if shares > 0 and (cash >= cost + commission + slippage):
                cash -= (cost + commission + slippage)
                position = Position(ts_code)
                position.add_long(shares, curr['close'])
                position.update_price(curr['close'])

                signals.append({
                    'date': curr['trade_date'],
                    'type': 'BUY',
                    'price': curr['close'],
                    'reason': signal_reason,
                    'indicators': {k: {kk: v[i] if v is not None else None for kk, v in ind.items()}
                                   for k, ind in indicators_data.items()}
                })
                daily_trade_count[curr['trade_date']] = daily_trade_count.get(curr['trade_date'], 0) + 1

        elif signal == 'SELL' and position and not position.is_empty:
            # 卖出
            realized_pnl = position.close_long(position.quantity, curr['close'])
            commission = position.quantity * curr['close'] * risk_cfg.commission_rate
            slippage = position.quantity * curr['close'] * risk_cfg.slippage_rate

            trades.append({
                'buy_date': data[i - 1]['trade_date'] if i > 0 else curr['trade_date'],
                'buy_price': round(position.avg_cost, 3),
                'sell_date': curr['trade_date'],
                'sell_price': round(curr['close'], 3),
                'profit': round(realized_pnl - commission - slippage, 2),
                'profit_pct': round((curr['close'] - position.avg_cost) / position.avg_cost, 4),
                'holding_days': 1,
                'sell_reason': signal_reason,
                'commission': round(commission, 2),
                'slippage': round(slippage, 2),
            })

            cash += position.quantity * curr['close'] - commission - slippage
            position = None

            signals.append({
                'date': curr['trade_date'],
                'type': 'SELL',
                'price': curr['close'],
                'reason': signal_reason,
            })
            daily_trade_count[curr['trade_date']] = daily_trade_count.get(curr['trade_date'], 0) + 1

        # 风控检查
        if position and not position.is_empty:
            # 止损检查
            should_stop, stop_reason = risk_mgr.check_stop_loss(position, curr['close'])
            if should_stop:
                realized_pnl = position.close_long(position.quantity, curr['close'])
                commission = position.quantity * curr['close'] * risk_cfg.commission_rate
                slippage = position.quantity * curr['close'] * risk_cfg.slippage_rate

                trades.append({
                    'buy_date': data[i - 1]['trade_date'] if i > 0 else curr['trade_date'],
                    'buy_price': round(position.avg_cost, 3),
                    'sell_date': curr['trade_date'],
                    'sell_price': round(curr['close'], 3),
                    'profit': round(realized_pnl - commission - slippage, 2),
                    'profit_pct': round((curr['close'] - position.avg_cost) / position.avg_cost, 4),
                    'holding_days': 1,
                    'sell_reason': stop_reason,
                    'commission': round(commission, 2),
                    'slippage': round(slippage, 2),
                })

                cash += position.quantity * curr['close'] - commission - slippage
                position = None

                signals.append({
                    'date': curr['trade_date'],
                    'type': 'SELL',
                    'price': curr['close'],
                    'reason': stop_reason,
                })
                continue

            # 止盈检查
            should_tp, tp_reason = risk_mgr.check_take_profit(position, curr['close'])
            if should_tp:
                realized_pnl = position.close_long(position.quantity, curr['close'])
                commission = position.quantity * curr['close'] * risk_cfg.commission_rate
                slippage = position.quantity * curr['close'] * risk_cfg.slippage_rate

                trades.append({
                    'buy_date': data[i - 1]['trade_date'] if i > 0 else curr['trade_date'],
                    'buy_price': round(position.avg_cost, 3),
                    'sell_date': curr['trade_date'],
                    'sell_price': round(curr['close'], 3),
                    'profit': round(realized_pnl - commission - slippage, 2),
                    'profit_pct': round((curr['close'] - position.avg_cost) / position.avg_cost, 4),
                    'holding_days': 1,
                    'sell_reason': tp_reason,
                    'commission': round(commission, 2),
                    'slippage': round(slippage, 2),
                })

                cash += position.quantity * curr['close'] - commission - slippage
                position = None

                signals.append({
                    'date': curr['trade_date'],
                    'type': 'SELL',
                    'price': curr['close'],
                    'reason': tp_reason,
                })
                continue

    # 平仓
    if position and not position.is_empty:
        last = data[-1]
        realized_pnl = position.close_long(position.quantity, last['close'])
        commission = position.quantity * last['close'] * risk_cfg.commission_rate
        slippage = position.quantity * last['close'] * risk_cfg.slippage_rate

        trades.append({
            'buy_date': data[0]['trade_date'],
            'buy_price': round(position.avg_cost, 3),
            'sell_date': last['trade_date'],
            'sell_price': round(last['close'], 3),
            'profit': round(realized_pnl - commission - slippage, 2),
            'profit_pct': round((last['close'] - position.avg_cost) / position.avg_cost, 4),
            'holding_days': 1,
            'sell_reason': '回测结束',
            'commission': round(commission, 2),
            'slippage': round(slippage, 2),
        })

        cash += position.quantity * last['close'] - commission - slippage
        position = None

    # 计算最终指标
    risk_metrics = risk_mgr.calculate_metrics()

    # 胜率统计
    winning_trades = [t for t in trades if t.get('profit', 0) > 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0

    # 盈亏比
    avg_profit = sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    losing_trades = [t for t in trades if t.get('profit', 0) <= 0]
    avg_loss = abs(sum(t['profit'] for t in losing_trades) / len(losing_trades)) if losing_trades else 1
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    # 平均持仓天数
    avg_holding_days = sum(t.get('holding_days', 0) for t in trades) / len(trades) if trades else 0

    return {
        'success': True,
        'result': {
            'summary': {
                'total_return': risk_metrics['total_return'],
                'annual_return': risk_metrics['annual_return'],
                'sharpe_ratio': risk_metrics['sharpe_ratio'],
                'max_drawdown': risk_metrics['max_drawdown'],
                'win_rate': round(win_rate, 4),
                'profit_loss_ratio': round(profit_loss_ratio, 2),
                'total_trades': len(trades),
                'avg_holding_days': round(avg_holding_days, 1),
                'var_95': risk_metrics['var_95'],
                'cvar_95': risk_metrics['cvar_95'],
            },
            'equity_curve': equity_curve,
            'trades': trades,
            'signals': signals,
            'indicators': indicators_data,
        }
    }


if __name__ == '__main__':
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            params = {}
        else:
            params = json.loads(input_data)

        result = run_backtest(params)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False))
        sys.exit(1)
