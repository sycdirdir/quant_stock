/**
 * 实时行情 Hook
 * 用于在组件中订阅和管理实时行情
 */

import { useEffect, useCallback, useState, useRef } from 'react'
import { StreamMessage, QuoteData, StreamStatus } from '../store/stream'

// 全局连接状态
let globalConnected = false
const listeners: Set<(msg: StreamMessage) => void> = new Set()

export function useStream() {
  const [connected, setConnected] = useState(globalConnected)
  const [status, setStatus] = useState<StreamStatus>({
    connected: false,
    subscribedCodes: []
  })
  const unsubscribeRef = useRef<(() => void) | null>(null)

  // 初始化连接
  useEffect(() => {
    const init = async () => {
      // 连接 WebSocket
      await window.api.stream.connect()

      // 订阅消息
      unsubscribeRef.current = window.api.stream.onMessage((msg: StreamMessage) => {
        // 更新连接状态
        if (msg.type === 'connected') {
          globalConnected = true
          setConnected(true)
          setStatus(prev => ({ ...prev, connected: true }))
        } else if (msg.type === 'disconnected') {
          globalConnected = false
          setConnected(false)
          setStatus(prev => ({ ...prev, connected: false }))
        }

        // 转发给所有监听器
        listeners.forEach(cb => cb(msg))
      })

      // 获取状态
      const statusResult = await window.api.stream.getStatus()
      if (statusResult.success) {
        setStatus(prev => ({ ...prev, connected: statusResult.data.connected }))
      }
    }

    init()

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current()
      }
    }
  }, [])

  // 订阅股票
  const subscribe = useCallback(async (tsCodes: string[]) => {
    const result = await window.api.stream.subscribe(tsCodes)
    if (result.success) {
      setStatus(prev => ({
        ...prev,
        subscribedCodes: [...new Set([...prev.subscribedCodes, ...tsCodes])]
      }))
    }
    return result
  }, [])

  // 取消订阅
  const unsubscribe = useCallback(async (tsCodes: string[]) => {
    const result = await window.api.stream.unsubscribe(tsCodes)
    if (result.success) {
      setStatus(prev => ({
        ...prev,
        subscribedCodes: prev.subscribedCodes.filter(c => !tsCodes.includes(c))
      }))
    }
    return result
  }, [])

  // 断开连接
  const disconnect = useCallback(async () => {
    await window.api.stream.disconnect()
    globalConnected = false
    setConnected(false)
    setStatus({ connected: false, subscribedCodes: [] })
  }, [])

  return {
    connected,
    status,
    subscribe,
    unsubscribe,
    disconnect
  }
}

// 监听实时行情
export function useRealtimeQuote(
  tsCode: string | null,
  onQuote?: (quote: QuoteData) => void
) {
  const { subscribe, unsubscribe, connected } = useStream()
  const quoteRef = useRef<QuoteData | null>(null)
  const [quote, setQuote] = useState<QuoteData | null>(null)

  // 订阅消息
  useEffect(() => {
    const unsubscribe = window.api.stream.onMessage((msg: StreamMessage) => {
      if (msg.type === 'quote' && msg.ts_code === tsCode) {
        quoteRef.current = msg.data
        setQuote(msg.data)
        onQuote?.(msg.data)
      } else if (msg.type === 'quote_delta' && msg.ts_code === tsCode) {
        // 增量更新
        const updated = { ...quoteRef.current, ...msg.data }
        quoteRef.current = updated
        setQuote(updated)
        onQuote?.(updated)
      }
    })

    return unsubscribe
  }, [tsCode, onQuote])

  // 订阅/取消订阅
  useEffect(() => {
    if (tsCode && connected) {
      subscribe([tsCode])
    }

    return () => {
      if (tsCode) {
        unsubscribe([tsCode])
      }
    }
  }, [tsCode, connected, subscribe, unsubscribe])

  return { quote, connected }
}

// 全局行情监听器
export function addStreamListener(callback: (msg: StreamMessage) => void) {
  listeners.add(callback)
  return () => listeners.delete(callback)
}

// 获取最新行情
export function getLatestQuote(tsCode: string): QuoteData | null {
  // 从全局存储获取最新行情
  return globalQuotes.get(tsCode) || null
}

// 全局行情存储
const globalQuotes: Map<string, QuoteData> = new Map()

// 自动更新全局行情
if (typeof window !== 'undefined') {
  window.api?.stream?.onMessage?.((msg: StreamMessage) => {
    if (msg.type === 'quote') {
      globalQuotes.set(msg.ts_code, msg.data)
    } else if (msg.type === 'quote_delta' && msg.ts_code) {
      // 增量更新：合并到现有行情
      const existing = globalQuotes.get(msg.ts_code) || {}
      const updated = { ...existing, ...msg.data }
      globalQuotes.set(msg.ts_code, updated)
    }
  })
}
