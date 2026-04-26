import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// K线数据项
export interface KlineItem {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount?: number
  ma5?: number
  ma10?: number
  ma20?: number
}

// 股票项
export interface Stock {
  ts_code: string
  symbol: string
  name: string
  area: string
  industry: string
  market: string
}

// 策略
export interface Strategy {
  id: number
  name: string
  description?: string
  config_json: string
  code?: string
}

// 回测结果摘要
export interface BacktestSummary {
  total_return: number
  annual_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  profit_loss_ratio: number
  total_trades: number
  avg_holding_days: number
}

// 交易记录
export interface Trade {
  buy_date: string
  buy_price: number
  sell_date?: string
  sell_price?: number
  profit?: number
  profit_pct?: number
  holding_days?: number
  sell_reason?: string
}

// 回测信号
export interface Signal {
  date: string
  type: 'BUY' | 'SELL'
  price: number
  reason: string
}

// 回测结果
export interface BacktestResult {
  summary: BacktestSummary
  equity_curve: { date: string; value: number }[]
  trades: Trade[]
  signals: Signal[]
}

// 策略配置（可视化）
export interface Condition {
  type: 'ma_cross' | 'kdj_cross' | 'macd_cross' | 'price_break'
  params: Record<string, any>
  logic: 'AND' | 'OR'
}

export interface StrategyConfig {
  name: string
  conditions: Condition[]
  risk: {
    stopLoss: number
    takeProfit: number
    positionSize: number
    maxDailyTrades: number
    maxPositionRatio: number
  }
}

interface AppState {
  // 认证
  user: { user_id: string; nickname: string; avatar_url?: string } | null
  jwtToken: string | null

  // 股票
  stocks: Stock[]
  selectedStock: Stock | null
  stockSearch: string

  // K线
  klineData: KlineItem[]
  klineLoading: boolean

  // 策略
  strategies: Strategy[]
  currentStrategy: StrategyConfig

  // 回测
  backtestResult: BacktestResult | null
  backtestRunning: boolean
  backtestProgress: number

  // 时间轴播放
  playing: boolean
  playSpeed: number
  currentIndex: number

  // Actions
  setUser: (user: AppState['user']) => void
  setJwtToken: (token: string | null) => void
  setStocks: (stocks: Stock[]) => void
  setSelectedStock: (stock: Stock | null) => void
  setStockSearch: (search: string) => void
  setKlineData: (data: KlineItem[]) => void
  setKlineLoading: (loading: boolean) => void
  setStrategies: (strategies: Strategy[]) => void
  setCurrentStrategy: (strategy: StrategyConfig) => void
  setBacktestResult: (result: BacktestResult | null) => void
  setBacktestRunning: (running: boolean) => void
  setBacktestProgress: (progress: number) => void
  setPlaying: (playing: boolean) => void
  setPlaySpeed: (speed: number) => void
  setCurrentIndex: (index: number) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // 初始状态
      user: null,
      jwtToken: null,
      stocks: [],
      selectedStock: null,
      stockSearch: '',
      klineData: [],
      klineLoading: false,
      strategies: [],
      currentStrategy: {
        name: '',
        conditions: [],
        risk: {
          stopLoss: 5,
          takeProfit: 10,
          positionSize: 20000,
          maxDailyTrades: 3,
          maxPositionRatio: 30
        }
      },
      backtestResult: null,
      backtestRunning: false,
      backtestProgress: 0,
      playing: false,
      playSpeed: 1,
      currentIndex: 0,

      // Actions
      setUser: (user) => set({ user }),
      setJwtToken: (token) => set({ jwtToken: token }),
      setStocks: (stocks) => set({ stocks }),
      setSelectedStock: (stock) => set({ selectedStock: stock }),
      setStockSearch: (search) => set({ stockSearch: search }),
      setKlineData: (data) => set({ klineData: data }),
      setKlineLoading: (loading) => set({ klineLoading: loading }),
      setStrategies: (strategies) => set({ strategies }),
      setCurrentStrategy: (strategy) => set({ currentStrategy: strategy }),
      setBacktestResult: (result) => set({ backtestResult: result }),
      setBacktestRunning: (running) => set({ backtestRunning: running }),
      setBacktestProgress: (progress) => set({ backtestProgress: progress }),
      setPlaying: (playing) => set({ playing }),
      setPlaySpeed: (speed) => set({ playSpeed: speed }),
      setCurrentIndex: (index) => set({ currentIndex: index })
    }),
    {
      name: 'quant-app-storage',
      partialize: (state) => ({
        jwtToken: state.jwtToken,
        user: state.user,
        strategies: state.strategies
      })
    }
  )
)
