import React, { useState, useEffect } from 'react'
import { useAppStore, Stock } from '../store'

export function StockSelect() {
  const {
    stocks,
    setStocks,
    selectedStock,
    setSelectedStock,
    stockSearch,
    setStockSearch,
    setKlineData,
    setKlineLoading
  } = useAppStore()

  const [loading, setLoading] = useState(false)

  const loadStocks = async (search: string = '') => {
    setLoading(true)
    try {
      const res = await window.api.stocks.list({ search, pageSize: 50 })
      if (res.success) {
        setStocks(res.data.items)
      }
    } catch (e) {
      console.error('loadStocks error', e)
    }
    setLoading(false)
  }

  useEffect(() => {
    loadStocks()
  }, [])

  // 防抖搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      loadStocks(stockSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [stockSearch])

  const handleSelect = async (stock: Stock) => {
    setSelectedStock(stock)
    setKlineLoading(true)

    // 加载日线数据
    try {
      const res = await window.api.kline.get({
        tsCode: stock.ts_code,
        period: 'daily',
        startDate: '20221010',
        endDate: '20260424'
      })
      if (res.success) {
        setKlineData(res.data.items)
      }
    } catch (e) {
      console.error('loadKline error', e)
    }
    setKlineLoading(false)
  }

  return (
    <div className="stock-search">
      <input
        type="text"
        placeholder="搜索股票名称/代码..."
        value={stockSearch}
        onChange={(e) => setStockSearch(e.target.value)}
      />

      <div className="stock-list">
        {loading ? (
          <div style={{ padding: '12px', color: '#6b7280', fontSize: '12px' }}>
            加载中...
          </div>
        ) : (
          stocks.map((stock) => (
            <div
              key={stock.ts_code}
              className={`stock-item ${selectedStock?.ts_code === stock.ts_code ? 'active' : ''}`}
              onClick={() => handleSelect(stock)}
            >
              <div className="name">{stock.name}</div>
              <div className="code">{stock.ts_code}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
