import React, { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { useAppStore, KlineItem } from '../store'

export function KLineChart() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts>()
  const { klineData, selectedStock, backtestResult } = useAppStore()

  useEffect(() => {
    if (!chartRef.current) return

    chartInstance.current = echarts.init(chartRef.current)

    const handleResize = () => {
      chartInstance.current?.resize()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chartInstance.current?.dispose()
    }
  }, [])

  useEffect(() => {
    if (!chartInstance.current || klineData.length === 0) return

    const dates = klineData.map((d) => d.trade_date)
    const ohlc = klineData.map((d) => [d.open, d.close, d.low, d.high])
    const vols = klineData.map((d) => ({
      value: d.vol,
      itemStyle: d.close >= d.open
        ? { color: '#ef5350', borderColor: '#ef5350' }
        : { color: '#26a69a', borderColor: '#26a69a' }
    }))

    // 计算均线
    const ma5 = calculateMA(5, klineData)
    const ma10 = calculateMA(10, klineData)
    const ma20 = calculateMA(20, klineData)

    // 买卖信号标记
    const buySignals: number[] = []
    const sellSignals: number[] = []
    const signalDates: string[] = []

    if (backtestResult?.signals) {
      backtestResult.signals.forEach((s) => {
        const idx = dates.indexOf(s.date)
        if (idx >= 0) {
          if (s.type === 'BUY') buySignals.push(idx)
          else sellSignals.push(idx)
          signalDates.push(`${s.type} ${s.price}`)
        }
      })
    }

    const option: echarts.EChartsOption = {
      backgroundColor: '#111827',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      legend: {
        top: 10,
        textStyle: { color: '#9ca3af' },
        data: ['K线', 'MA5', 'MA10', 'MA20']
      },
      grid: [
        { left: '8%', right: '5%', top: '15%', height: '55%' },
        { left: '8%', right: '5%', top: '75%', height: '15%' }
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#6b7280', fontSize: 10 } },
        { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { show: false } }
      ],
      yAxis: [
        { scale: true, gridIndex: 0, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#6b7280', fontSize: 10 }, splitLine: { lineStyle: { color: '#1f2937' } } },
        { scale: true, gridIndex: 1, axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#6b7280', fontSize: 10 } }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ohlc,
          itemStyle: {
            color: '#ef5350',
            color0: '#26a69a',
            borderColor: '#ef5350',
            borderColor0: '#26a69a'
          },
          markPoint: {
            data: [
              ...buySignals.map((idx) => ({
                coord: [idx, klineData[idx]?.low || 0],
                symbol: 'triangle',
                symbolSize: 12,
                color: '#10b981',
                label: { show: false }
              })),
              ...sellSignals.map((idx) => ({
                coord: [idx, klineData[idx]?.high || 0],
                symbol: 'triangle',
                symbolSize: 12,
                color: '#ef4444',
                label: { show: false }
              }))
            ]
          }
        },
        {
          name: 'MA5',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ma5,
          smooth: true,
          lineStyle: { width: 1, color: '#fbbf24' },
          symbol: 'none'
        },
        {
          name: 'MA10',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ma10,
          smooth: true,
          lineStyle: { width: 1, color: '#60a5fa' },
          symbol: 'none'
        },
        {
          name: 'MA20',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ma20,
          smooth: true,
          lineStyle: { width: 1, color: '#a78bfa' },
          symbol: 'none'
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: vols,
          barWidth: '60%'
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }
      ]
    }

    chartInstance.current.setOption(option, true)
  }, [klineData, selectedStock, backtestResult])

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
}

function calculateMA(period: number, data: KlineItem[]): (number | string)[] {
  const result: (number | string)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0)
      result.push(+(sum / period).toFixed(3))
    }
  }
  return result
}
