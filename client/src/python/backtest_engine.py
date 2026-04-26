#!/usr/bin/env python3
"""
量化交易回测引擎
接收 JSON 参数，输出 JSON 结果
"""

import sys
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


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


def detect_ma_cross(
    i: int,
    ma_fast_prev: float,
    ma_fast_curr: float,
    ma_slow_prev: float,
    ma_slow_curr: float
) -> Optional[str]:
    """检测均线交叉"""
    if ma_fast_prev <= ma_slow_prev and ma_fast_curr > ma_slow_curr:
        return 'BUY'
    elif ma_fast_prev >= ma_slow_prev and ma_fast_curr < ma_slow_curr:
        return 'SELL'
    return None


def run_backtest(params: Dict[str, Any]) -> Dict[str, Any]:
    """运行回测"""

    # 解析参数
    ts_code = params.get('ts_code', '')
    period = params.get('period', 'daily')
    start_date = params.get('start_date', '20250101')
    end_date = params.get('end_date', '20260424')
    initial_cash = params.get('initial_cash', 100000)

    strategy_config = params.get('strategy', {})
    risk_config = params.get('risk', {
        'stop_loss': 0.05,
        'take_profit': 0.10,
        'position_size': 20000,
        'max_daily_trades': 3,
        'max_position_ratio': 0.3
    })

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

    # 计算均线
    ma_periods = strategy_config.get('ma_periods', [5, 10, 20])
    ma_data = {}
    for p in ma_periods:
        ma_data[f'ma{p}'] = calculate_ma(data, p)

    # 交易模拟
    cash = initial_cash
    position = 0
    position_price = 0.0
    position_date = ''
    trades = []
    signals = []
    equity_curve = []

    # 统计
    daily_trade_count = {}

    fast_ma = ma_periods[0] if len(ma_periods) >= 1 else 5
    slow_ma = ma_periods[1] if len(ma_periods) >= 2 else 20

    for i in range(1, len(data)):
        curr = data[i]
        prev = data[i - 1]

        # 更新权益曲线
        equity = cash + position * curr['close']
        equity_curve.append({
            'date': curr['trade_date'],
            'value': round(equity, 2)
        })

        # 均线交叉检测
        ma_fast_prev = ma_data[f'ma{fast_ma}'][i - 1]
        ma_fast_curr = ma_data[f'ma{fast_ma}'][i]
        ma_slow_prev = ma_data[f'ma{slow_ma}'][i - 1]
        ma_slow_curr = ma_data[f'ma{slow_ma}'][i]

        if None in [ma_fast_prev, ma_fast_curr, ma_slow_prev, ma_slow_curr]:
            pass
        else:
            cross = detect_ma_cross(i, ma_fast_prev, ma_fast_curr, ma_slow_prev, ma_slow_curr)

            if cross == 'BUY' and position == 0:
                shares = int(risk_config['position_size'] / curr['close'] / 100) * 100
                if shares * curr['close'] <= cash and shares > 0:
                    cash -= shares * curr['close']
                    position = shares
                    position_price = curr['close']
                    position_date = curr['trade_date']
                    signals.append({
                        'date': curr['trade_date'],
                        'type': 'BUY',
                        'price': curr['close'],
                        'reason': f'MA{fast_ma}上穿MA{slow_ma}'
                    })
                    daily_trade_count[curr['trade_date']] = daily_trade_count.get(curr['trade_date'], 0) + 1

            elif cross == 'SELL' and position > 0:
                profit = position * (curr['close'] - position_price)
                profit_pct = (curr['close'] - position_price) / position_price
                holding_days = (datetime.strptime(curr['trade_date'], '%Y%m%d') -
                               datetime.strptime(position_date, '%Y%m%d')).days

                trades.append({
                    'buy_date': position_date,
                    'buy_price': round(position_price, 3),
                    'sell_date': curr['trade_date'],
                    'sell_price': round(curr['close'], 3),
                    'profit': round(profit, 2),
                    'profit_pct': round(profit_pct, 4),
                    'holding_days': holding_days
                })

                cash += position * curr['close']
                position = 0
                position_price = 0.0

                signals.append({
                    'date': curr['trade_date'],
                    'type': 'SELL',
                    'price': curr['close'],
                    'reason': f'MA{fast_ma}下穿MA{slow_ma}'
                })
                daily_trade_count[curr['trade_date']] = daily_trade_count.get(curr['trade_date'], 0) + 1

        # 风控检查
        if position > 0:
            loss_pct = (position_price - curr['close']) / position_price
            profit_pct = (curr['close'] - position_price) / position_price

            if loss_pct >= risk_config['stop_loss']:
                # 止损
                profit = position * (curr['close'] - position_price)
                holding_days = (datetime.strptime(curr['trade_date'], '%Y%m%d') -
                               datetime.strptime(position_date, '%Y%m%d')).days
                trades.append({
                    'buy_date': position_date,
                    'buy_price': round(position_price, 3),
                    'sell_date': curr['trade_date'],
                    'sell_price': round(curr['close'], 3),
                    'profit': round(profit, 2),
                    'profit_pct': round(-risk_config['stop_loss'], 4),
                    'holding_days': holding_days,
                    'sell_reason': '止损'
                })
                cash += position * curr['close']
                position = 0
                signals.append({
                    'date': curr['trade_date'],
                    'type': 'SELL',
                    'price': curr['close'],
                    'reason': f'止损-{loss_pct:.2%}'
                })

            elif profit_pct >= risk_config['take_profit']:
                # 止盈
                profit = position * (curr['close'] - position_price)
                holding_days = (datetime.strptime(curr['trade_date'], '%Y%m%d') -
                               datetime.strptime(position_date, '%Y%m%d')).days
                trades.append({
                    'buy_date': position_date,
                    'buy_price': round(position_price, 3),
                    'sell_date': curr['trade_date'],
                    'sell_price': round(curr['close'], 3),
                    'profit': round(profit, 2),
                    'profit_pct': round(profit_pct, 4),
                    'holding_days': holding_days,
                    'sell_reason': '止盈'
                })
                cash += position * curr['close']
                position = 0
                signals.append({
                    'date': curr['trade_date'],
                    'type': 'SELL',
                    'price': curr['close'],
                    'reason': f'止盈-{profit_pct:.2%}'
                })

    # 平仓
    if position > 0:
        last = data[-1]
        profit = position * (last['close'] - position_price)
        profit_pct = (last['close'] - position_price) / position_price
        holding_days = (datetime.strptime(last['trade_date'], '%Y%m%d') -
                       datetime.strptime(position_date, '%Y%m%d')).days
        trades.append({
            'buy_date': position_date,
            'buy_price': round(position_price, 3),
            'sell_date': last['trade_date'],
            'sell_price': round(last['close'], 3),
            'profit': round(profit, 2),
            'profit_pct': round(profit_pct, 4),
            'holding_days': holding_days,
            'sell_reason': '回测结束'
        })
        cash += position * last['close']
        position = 0

    # 计算指标
    final_equity = cash
    total_return = (final_equity - initial_cash) / initial_cash

    years = (datetime.strptime(end_date, '%Y%m%d') -
             datetime.strptime(start_date, '%Y%m%d')).days / 365.25
    annual_return = total_return / years if years > 0 else 0

    # 夏普比率
    if len(equity_curve) > 1:
        returns = [(equity_curve[i]['value'] - equity_curve[i - 1]['value']) /
                   equity_curve[i - 1]['value']
                   for i in range(1, len(equity_curve))]
        avg_return = sum(returns) / len(returns) if returns else 0
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1
        sharpe = ((avg_return - 0.03 / 252) / std_return * (252 ** 0.5)) if std_return > 0 else 0
    else:
        sharpe = 0

    # 最大回撤
    peak = initial_cash
    max_drawdown = 0
    for e in equity_curve:
        if e['value'] > peak:
            peak = e['value']
        dd = (e['value'] - peak) / peak
        if dd < max_drawdown:
            max_drawdown = dd

    # 胜率
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
                'total_return': round(total_return, 4),
                'annual_return': round(annual_return, 4),
                'sharpe_ratio': round(sharpe, 2),
                'max_drawdown': round(max_drawdown, 4),
                'win_rate': round(win_rate, 4),
                'profit_loss_ratio': round(profit_loss_ratio, 2),
                'total_trades': len(trades),
                'avg_holding_days': round(avg_holding_days, 1)
            },
            'equity_curve': equity_curve,
            'trades': trades,
            'signals': signals
        }
    }


if __name__ == '__main__':
    try:
        # 从 stdin 读取 JSON
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
