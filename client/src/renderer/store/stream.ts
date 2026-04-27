/**
 * 实时行情 WebSocket 类型定义
 */

// 行情数据
export interface QuoteData {
  last: number       // 最新价
  open: number       // 开盘价
  high: number       // 最高价
  low: number        // 最低价
  volume: number     // 成交量
  amount: number     // 成交额
  change: number     // 涨跌幅
  prev_close: number // 昨收价
  timestamp: string  // 时间戳
}

// K线数据
export interface KlineData {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// 交易信号
export interface SignalData {
  type: 'BUY' | 'SELL'
  price: number
  reason: string
}

// WebSocket 消息类型
export type StreamMessage =
  | { type: 'connected'; data: { server_time: string; active_connections: number } }
  | { type: 'disconnected'; data: { status: string } }
  | { type: 'quote'; ts_code: string; data: QuoteData; timestamp: string }
  | { type: 'quote_delta'; ts_code: string; data: Partial<QuoteData> & { _changed_fields?: string[] }; timestamp: string }
  | { type: 'kline'; ts_code: string; data: KlineData; timestamp: string }
  | { type: 'signal'; ts_code: string; data: SignalData; timestamp: string }
  | { type: 'ping'; timestamp: string }
  | { type: 'subscribed'; ts_codes: string[] }
  | { type: 'unsubscribed'; ts_codes: string[] }
  | { type: 'quotes'; data: Record<string, QuoteData> }

// 流服务状态
export interface StreamStatus {
  connected: boolean
  subscribedCodes: string[]
}
