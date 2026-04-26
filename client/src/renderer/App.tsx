import React, { useEffect } from 'react'
import { useAppStore } from './store'
import { KLineChart } from './components/KLineChart'
import { StockSelect } from './components/StockSelect'
import { StrategyEditor } from './components/StrategyEditor'
import { BacktestPanel } from './components/BacktestPanel'
import { LoginScreen } from './components/LoginScreen'

declare global {
  interface Window {
    api: {
      stocks: {
        list: (params: { page?: number; pageSize?: number; search?: string }) => Promise<any>
      }
      kline: {
        get: (params: { tsCode: string; period: string; startDate: string; endDate: string }) => Promise<any>
      }
      backtest: {
        run: (params: any) => Promise<any>
      }
      strategy: {
        save: (strategy: { name: string; description?: string; configJson: string; code?: string }) => Promise<any>
        list: () => Promise<any>
      }
      data: {
        download: (params: { tsCode: string; period: string; startDate: string; endDate: string }) => Promise<any>
      }
      auth: {
        wechatQr: () => Promise<any>
        wechatLogin: (code: string) => Promise<any>
      }
    }
  }
}

export default function App() {
  const { user, jwtToken, setUser, setJwtToken } = useAppStore()

  // 检查本地存储的认证状态
  useEffect(() => {
    const stored = localStorage.getItem('quant-app-storage')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed.state?.jwtToken) {
          setJwtToken(parsed.state.jwtToken)
          setUser(parsed.state.user)
        }
      } catch {
        // ignore
      }
    }
  }, [])

  if (!user) {
    return <LoginScreen />
  }

  return (
    <div className="app-layout">
      {/* 左侧边栏 */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>量化交易模拟</h1>
        </div>
        <div className="sidebar-content">
          <StockSelect />
        </div>
      </div>

      {/* 主内容区 */}
      <div className="main-content">
        <TopBar />
        <div className="content-area">
          <div className="chart-container">
            <KLineChart />
          </div>
          <BottomPanels />
        </div>
      </div>
    </div>
  )
}

function TopBar() {
  const { selectedStock, setBacktestRunning, backtestRunning } = useAppStore()

  return (
    <div className="top-bar">
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '16px' }}>
        {selectedStock ? (
          <>
            <span style={{ color: '#60a5fa', fontWeight: 600 }}>
              {selectedStock.name}
            </span>
            <span style={{ color: '#6b7280', fontSize: '12px' }}>
              {selectedStock.ts_code}
            </span>
            <span style={{ color: '#6b7280', fontSize: '12px' }}>
              {selectedStock.industry}
            </span>
          </>
        ) : (
          <span style={{ color: '#6b7280', fontSize: '13px' }}>
            请在左侧选择股票
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          className="btn btn-primary"
          disabled={!selectedStock || backtestRunning}
          onClick={() => setBacktestRunning(true)}
        >
          运行回测
        </button>
      </div>
    </div>
  )
}

function BottomPanels() {
  const [activeTab, setActiveTab] = React.useState<'strategy' | 'result'>('strategy')

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="tabs">
        <div
          className={`tab ${activeTab === 'strategy' ? 'active' : ''}`}
          onClick={() => setActiveTab('strategy')}
        >
          策略配置
        </div>
        <div
          className={`tab ${activeTab === 'result' ? 'active' : ''}`}
          onClick={() => setActiveTab('result')}
        >
          回测结果
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'strategy' ? <StrategyEditor /> : <BacktestPanel />}
      </div>
    </div>
  )
}
