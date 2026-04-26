import React, { useState, useEffect } from 'react'
import { useAppStore, BacktestResult } from '../store'

export function BacktestPanel() {
  const {
    selectedStock,
    currentStrategy,
    backtestResult,
    setBacktestResult,
    backtestRunning,
    setBacktestRunning,
    klineData
  } = useAppStore()

  const [startDate, setStartDate] = useState('20221010')
  const [endDate, setEndDate] = useState('20260424')

  // 加载已有回测结果
  useEffect(() => {
    // 从 store 读取
  }, [])

  const runBacktest = async () => {
    if (!selectedStock) {
      alert('请先选择股票')
      return
    }

    if (currentStrategy.conditions.length === 0) {
      alert('请至少添加一个条件')
      return
    }

    setBacktestRunning(true)

    try {
      // 直接在前端计算（简单策略）
      const result = calculateBacktest(
        klineData,
        currentStrategy,
        startDate,
        endDate
      )
      setBacktestResult(result)
    } catch (e: any) {
      console.error('backtest error', e)
      alert('回测失败: ' + e.message)
    }

    setBacktestRunning(false)
  }

  if (!backtestResult) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <div style={{ marginBottom: '16px' }}>暂无回测结果</div>
        <button
          className="btn btn-primary"
          onClick={runBacktest}
          disabled={!selectedStock || backtestRunning || klineData.length === 0}
        >
          {backtestRunning ? '回测中...' : '运行回测'}
        </button>
      </div>
    )
  }

  const s = backtestResult.summary

  return (
    <div style={{ overflow: 'auto', height: '100%' }}>
      {/* 操作栏 */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #1f2937', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button
          className="btn btn-primary"
          onClick={runBacktest}
          disabled={!selectedStock || backtestRunning || klineData.length === 0}
        >
          {backtestRunning ? '回测中...' : '重新回测'}
        </button>
        <span style={{ fontSize: '12px', color: '#6b7280' }}>
          {selectedStock?.name} ({selectedStock?.ts_code})
        </span>
      </div>

      {/* 指标卡片 */}
      <div className="result-metrics">
        <div className="metric-card">
          <div className="label">总收益率</div>
          <div className={`value ${s.total_return >= 0 ? 'positive' : 'negative'}`}>
            {(s.total_return * 100).toFixed(2)}%
          </div>
        </div>
        <div className="metric-card">
          <div className="label">年化收益率</div>
          <div className={`value ${s.annual_return >= 0 ? 'positive' : 'negative'}`}>
            {(s.annual_return * 100).toFixed(2)}%
          </div>
        </div>
        <div className="metric-card">
          <div className="label">夏普比率</div>
          <div className="value">{s.sharpe_ratio.toFixed(2)}</div>
        </div>
        <div className="metric-card">
          <div className="label">最大回撤</div>
          <div className="value negative">{(s.max_drawdown * 100).toFixed(2)}%</div>
        </div>
        <div className="metric-card">
          <div className="label">胜率</div>
          <div className="value">{(s.win_rate * 100).toFixed(1)}%</div>
        </div>
        <div className="metric-card">
          <div className="label">盈亏比</div>
          <div className="value">{s.profit_loss_ratio.toFixed(2)}</div>
        </div>
        <div className="metric-card">
          <div className="label">交易次数</div>
          <div className="value">{s.total_trades}</div>
        </div>
        <div className="metric-card">
          <div className="label">平均持仓天数</div>
          <div className="value">{s.avg_holding_days.toFixed(1)}</div>
        </div>
      </div>

      {/* 交易记录 */}
      {backtestResult.trades.length > 0 && (
        <div style={{ padding: '12px' }}>
          <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>
            交易记录
          </div>
          <div className="trade-list">
            {backtestResult.trades.map((t, i) => (
              <div key={i} className="trade-item">
                <div>
                  <span className="date">{t.buy_date}</span>
                  <span style={{ margin: '0 8px', color: '#4b5563' }}>→</span>
                  <span className="date">{t.sell_date || '持仓中'}</span>
                </div>
                <div>
                  <span style={{ color: '#9ca3af', marginRight: '8px' }}>
                    买入 {t.buy_price} → 卖出 {t.sell_price || '-'}
                  </span>
                  {t.profit_pct !== undefined && (
                    <span className={`type ${t.profit >= 0 ? 'buy' : 'sell'}`}>
                      {t.profit >= 0 ? '+' : ''}{(t.profit_pct * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// 简单的均线交叉回测（前端计算）
function calculateBacktest(
  klineData: any[],
  strategy: any,
  startDate: string,
  endDate: string
): BacktestResult {
  const data = klineData.filter(
    (d) => d.trade_date >= startDate && d.trade_date <= endDate
  )

  if (data.length === 0) {
    return {
      summary: { total_return: 0, annual_return: 0, sharpe_ratio: 0, max_drawdown: 0, win_rate: 0, profit_loss_ratio: 0, total_trades: 0, avg_holding_days: 0 },
      equity_curve: [],
      trades: [],
      signals: []
    }
  }

  // 计算均线
  const ma5 = calcMA(data, 5)
  const ma20 = calcMA(data, 20)

  const initialCash = 100000
  const risk = strategy.risk
  let cash = initialCash
  let position = 0
  let positionPrice = 0
  let positionDate = ''
  const trades: any[] = []
  const signals: any[] = []
  const equityCurve: { date: string; value: number }[] = []

  for (let i = 1; i < data.length; i++) {
    const prev = data[i - 1]
    const curr = data[i]

    // 更新权益
    const equity = cash + position * curr.close
    equityCurve.push({ date: curr.trade_date, value: equity })

    // 均线交叉信号
    const prevMA5 = ma5[i - 1]
    const currMA5 = ma5[i]
    const prevMA20 = ma20[i - 1]
    const currMA20 = ma20[i]

    if (prevMA5 && currMA5 && prevMA20 && currMA20) {
      // 买入信号：MA5 上穿 MA20
      if (prevMA5 <= prevMA20 && currMA5 > currMA20 && position === 0) {
        const shares = Math.floor(risk.positionSize / curr.close / 100) * 100
        if (shares > 0) {
          cash -= shares * curr.close
          position = shares
          positionPrice = curr.close
          positionDate = curr.trade_date
          signals.push({ date: curr.trade_date, type: 'BUY', price: curr.close, reason: 'MA5上穿MA20' })
        }
      }
      // 卖出信号：MA5 下穿 MA20
      else if (prevMA5 >= prevMA20 && currMA5 < currMA20 && position > 0) {
        const profit = (curr.close - positionPrice) / positionPrice
        trades.push({
          buy_date: positionDate,
          buy_price: positionPrice,
          sell_date: curr.trade_date,
          sell_price: curr.close,
          profit: position * (curr.close - positionPrice),
          profit_pct: profit,
          holding_days: Math.round((new Date(curr.trade_date).getTime() - new Date(positionDate).getTime()) / 86400000)
        })
        cash += position * curr.close
        position = 0
        positionPrice = 0
        signals.push({ date: curr.trade_date, type: 'SELL', price: curr.close, reason: 'MA5下穿MA20' })
      }
    }

    // 风控检查
    if (position > 0) {
      const lossPct = (positionPrice - curr.close) / positionPrice
      const profitPct = (curr.close - positionPrice) / positionPrice
      if (lossPct >= risk.stopLoss / 100) {
        trades.push({
          buy_date: positionDate,
          buy_price: positionPrice,
          sell_date: curr.trade_date,
          sell_price: curr.close,
          profit: position * (curr.close - positionPrice),
          profit_pct: lossPct,
          holding_days: Math.round((new Date(curr.trade_date).getTime() - new Date(positionDate).getTime()) / 86400000),
          sell_reason: '止损'
        })
        cash += position * curr.close
        position = 0
        positionPrice = 0
        signals.push({ date: curr.trade_date, type: 'SELL', price: curr.close, reason: '止损' })
      } else if (profitPct >= risk.takeProfit / 100) {
        trades.push({
          buy_date: positionDate,
          buy_price: positionPrice,
          sell_date: curr.trade_date,
          sell_price: curr.close,
          profit: position * (curr.close - positionPrice),
          profit_pct: profitPct,
          holding_days: Math.round((new Date(curr.trade_date).getTime() - new Date(positionDate).getTime()) / 86400000),
          sell_reason: '止盈'
        })
        cash += position * curr.close
        position = 0
        positionPrice = 0
        signals.push({ date: curr.trade_date, type: 'SELL', price: curr.close, reason: '止盈' })
      }
    }
  }

  // 平仓
  if (position > 0) {
    const last = data[data.length - 1]
    trades.push({
      buy_date: positionDate,
      buy_price: positionPrice,
      sell_date: last.trade_date,
      sell_price: last.close,
      profit: position * (last.close - positionPrice),
      profit_pct: (last.close - positionPrice) / positionPrice,
      holding_days: Math.round((new Date(last.trade_date).getTime() - new Date(positionDate).getTime()) / 86400000),
      sell_reason: '回测结束'
    })
    cash += position * last.close
    position = 0
  }

  const finalEquity = cash
  const totalReturn = (finalEquity - initialCash) / initialCash
  const years = (new Date(endDate).getTime() - new Date(startDate).getTime()) / (365 * 86400000 * 1000)
  const annualReturn = totalReturn / years

  // 计算夏普
  const returns = equityCurve.map((e, i) =>
    i > 0 ? (e.value - equityCurve[i - 1].value) / equityCurve[i - 1].value : 0
  )
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
  const stdReturn = Math.sqrt(returns.map((r) => (r - avgReturn) ** 2).reduce((a, b) => a + b, 0) / returns.length)
  const sharpe = stdReturn > 0 ? (avgReturn - 0.03 / 252) / stdReturn * Math.sqrt(252) : 0

  // 计算最大回撤
  let maxDrawdown = 0
  let peak = initialCash
  for (const e of equityCurve) {
    if (e.value > peak) peak = e.value
    const dd = (e.value - peak) / peak
    if (dd < maxDrawdown) maxDrawdown = dd
  }

  // 胜率
  const winning = trades.filter((t) => t.profit > 0).length
  const winRate = trades.length > 0 ? winning / trades.length : 0

  // 盈亏比
  const avgProfit = trades.filter((t) => t.profit > 0).reduce((a, b) => a + b.profit, 0) / (winning || 1)
  const avgLoss = Math.abs(trades.filter((t) => t.profit <= 0).reduce((a, b) => a + b.profit, 0)) / (trades.length - winning || 1)
  const profitLossRatio = avgLoss > 0 ? avgProfit / avgLoss : 0

  // 平均持仓天数
  const avgHoldingDays = trades.length > 0
    ? trades.reduce((a, t) => a + (t.holding_days || 0), 0) / trades.length
    : 0

  return {
    summary: {
      total_return: totalReturn,
      annual_return: annualReturn,
      sharpe_ratio: sharpe,
      max_drawdown: maxDrawdown,
      win_rate: winRate,
      profit_loss_ratio: profitLossRatio,
      total_trades: trades.length,
      avg_holding_days: avgHoldingDays
    },
    equity_curve: equityCurve,
    trades,
    signals
  }
}

function calcMA(data: any[], period: number): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((a: number, d: any) => a + d.close, 0)
      result.push(+(sum / period).toFixed(3))
    }
  }
  return result
}
