import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { spawn, ChildProcess } from 'child_process'
import log from 'electron-log'

log.initialize()
log.info('应用启动...')

let mainWindow: BrowserWindow | null = null

// WebSocket 连接管理
let wsConnection: WebSocket | null = null
let wsReconnectTimer: NodeJS.Timeout | null = null
let wsReconnectAttempts = 0
const WS_URL = 'ws://localhost:8000/ws/stream'
const WS_MAX_RECONNECT_DELAY = 30000  // 最大重连延迟 30秒
const WS_BASE_RECONNECT_DELAY = 1000  // 基础重连延迟 1秒

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: '量化交易模拟平台',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  log.info('主窗口创建完成')
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// ============================================================
// IPC 处理：股票列表
// ============================================================
ipcMain.handle('stocks:list', async (_event, params: { page?: number; pageSize?: number; search?: string }) => {
  try {
    const response = await fetch(
      `http://localhost:8000/api/stocks?page=${params.page || 1}&pageSize=${params.pageSize || 20}&search=${params.search || ''}`
    )
    const data = await response.json()
    return data
  } catch (error: any) {
    log.error('stocks:list error:', error.message)
    return { success: false, error: error.message }
  }
})

// ============================================================
// IPC 处理：K线数据
// ============================================================
ipcMain.handle('kline:get', async (_event, params: {
  tsCode: string
  period: string
  startDate: string
  endDate: string
}) => {
  try {
    const url = `http://localhost:8000/api/data/download/${params.tsCode}?period=${params.period}&startDate=${params.startDate}&endDate=${params.endDate}`
    const response = await fetch(url)
    const data = await response.json()
    return data
  } catch (error: any) {
    log.error('kline:get error:', error.message)
    return { success: false, error: error.message }
  }
})

// ============================================================
// IPC 处理：运行回测
// ============================================================
let backtestProcess: ChildProcess | null = null

ipcMain.handle('backtest:run', async (event, params: {
  tsCode: string
  period: string
  startDate: string
  endDate: string
  initialCash: number
  strategy: any
  risk: any
}) => {
  return new Promise((resolve) => {
    try {
      // 启动 Python 回测子进程
      backtestProcess = spawn('python3', [
        join(__dirname, '../python/backtest_engine.py'),
        JSON.stringify(params)
      ])

      let output = ''

      backtestProcess.stdout?.on('data', (data: Buffer) => {
        output += data.toString()
        try {
          const result = JSON.parse(output)
          backtestProcess = null
          resolve({ success: true, result })
        } catch {
          // 还没接收完，继续等待
        }
      })

      backtestProcess.stderr?.on('data', (data: Buffer) => {
        log.error('backtest stderr:', data.toString())
      })

      backtestProcess.on('error', (error: any) => {
        backtestProcess = null
        resolve({ success: false, error: error.message })
      })

    } catch (error: any) {
      resolve({ success: false, error: error.message })
    }
  })
})

// ============================================================
// IPC 处理：策略保存
// ============================================================
ipcMain.handle('strategy:save', async (_event, strategy: {
  name: string
  description?: string
  configJson: string
  code?: string
}) => {
  try {
    // 存入本地 SQLite
    const Database = require('better-sqlite3')
    const dbPath = join(app.getPath('userData'), 'quant.db')
    const db = new Database(dbPath)

    db.exec(`
      CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        name TEXT NOT NULL,
        description TEXT,
        config_json TEXT NOT NULL,
        code TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        synced INTEGER DEFAULT 0
      )
    `)

    const stmt = db.prepare(`
      INSERT INTO strategies (name, description, config_json, code)
      VALUES (?, ?, ?, ?)
    `)
    const result = stmt.run(
      strategy.name,
      strategy.description || '',
      strategy.configJson,
      strategy.code || ''
    )

    db.close()
    return { success: true, data: { id: result.lastInsertRowid } }

  } catch (error: any) {
    log.error('strategy:save error:', error.message)
    return { success: false, error: error.message }
  }
})

// ============================================================
// IPC 处理：策略列表
// ============================================================
ipcMain.handle('strategy:list', async () => {
  try {
    const Database = require('better-sqlite3')
    const dbPath = join(app.getPath('userData'), 'quant.db')
    const db = new Database(dbPath)

    const rows = db.prepare('SELECT * FROM strategies ORDER BY updated_at DESC').all()
    db.close()
    return { success: true, data: rows }

  } catch (error: any) {
    log.error('strategy:list error:', error.message)
    return { success: false, error: error.message }
  }
})

// ============================================================
// IPC 处理：数据下载
// ============================================================
ipcMain.handle('data:download', async (_event, params: {
  tsCode: string
  period: string
  startDate: string
  endDate: string
}) => {
  try {
    const Database = require('better-sqlite3')
    const dbPath = join(app.getPath('userData'), 'quant.db')
    const db = new Database(dbPath)

    // 初始化表
    db.exec(`
      CREATE TABLE IF NOT EXISTS daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_code TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL,
        pre_close REAL, change REAL, pct_chg REAL,
        vol REAL, amount REAL,
        UNIQUE(ts_code, trade_date)
      )
    `)

    // 从服务端获取数据
    const url = `http://localhost:8000/api/data/download/${params.tsCode}?period=${params.period}&startDate=${params.startDate}&endDate=${params.endDate}`
    const response = await fetch(url)
    const data = await response.json()

    if (!data.success) {
      db.close()
      return { success: false, error: data.error }
    }

    // 插入本地 SQLite
    const insert = db.prepare(`
      INSERT OR REPLACE INTO daily
      (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)

    const insertMany = db.transaction((items: any[]) => {
      for (const item of items) {
        insert.run(
          params.tsCode,
          item.trade_date,
          item.open, item.high, item.low, item.close,
          item.pre_close, item.change, item.pct_chg,
          item.vol, item.amount
        )
      }
    })

    insertMany(data.data.items)
    db.close()

    return { success: true, data: { downloaded: data.data.items.length } }

  } catch (error: any) {
    log.error('data:download error:', error.message)
    return { success: false, error: error.message }
  }
})

// ============================================================
// IPC 处理：微信登录
// ============================================================
ipcMain.handle('auth:wechat_qr', async () => {
  try {
    const response = await fetch('http://localhost:8000/api/auth/wechat/qr')
    const data = await response.json()
    return data
  } catch (error: any) {
    return { success: false, error: error.message }
  }
})

ipcMain.handle('auth:wechat_login', async (_event, code: string) => {
  try {
    const response = await fetch('http://localhost:8000/api/auth/wechat/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    const data = await response.json()
    return data
  } catch (error: any) {
    return { success: false, error: error.message }
  }
})

log.info('IPC 处理器注册完成')

// ============================================================
// WebSocket 实时行情管理
// ============================================================

function connectWebSocket() {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    return
  }

  try {
    wsConnection = new WebSocket(WS_URL)

    wsConnection.onopen = () => {
      log.info('WebSocket 连接已建立')
      // 清除重连定时器
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer)
        wsReconnectTimer = null
      }
      // 重置重连计数
      wsReconnectAttempts = 0
      // 通知渲染进程
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('stream:connected', { status: 'connected' })
      }
    }

    wsConnection.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        // 转发到渲染进程
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('stream:message', message)
        }
      } catch (e) {
        log.error('WebSocket 消息解析失败:', e)
      }
    }

    wsConnection.onerror = (error) => {
      log.error('WebSocket 错误:', error)
    }

    wsConnection.onclose = () => {
      log.info('WebSocket 连接已关闭')
      wsConnection = null
      // 通知渲染进程
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('stream:disconnected', { status: 'disconnected' })
      }
      // 指数退避重连 (1s, 2s, 4s, 8s, 16s, 最大 30s)
      if (!wsReconnectTimer) {
        wsReconnectAttempts++
        const delay = Math.min(WS_BASE_RECONNECT_DELAY * Math.pow(2, wsReconnectAttempts - 1), WS_MAX_RECONNECT_DELAY)
        log.info(`WebSocket ${delay}ms 后重连 (第 ${wsReconnectAttempts} 次)`)
        wsReconnectTimer = setTimeout(() => {
          wsReconnectTimer = null
          connectWebSocket()
        }, delay)
      }
    }

  } catch (error: any) {
    log.error('WebSocket 连接失败:', error.message)
  }
}

function disconnectWebSocket() {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (wsConnection) {
    wsConnection.close()
    wsConnection = null
  }
}

// WebSocket IPC 处理器
ipcMain.handle('stream:connect', async () => {
  connectWebSocket()
  return { success: true }
})

ipcMain.handle('stream:disconnect', async () => {
  disconnectWebSocket()
  return { success: true }
})

ipcMain.handle('stream:subscribe', async (_event, tsCodes: string[]) => {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    wsConnection.send(JSON.stringify({
      type: 'subscribe',
      ts_codes: tsCodes
    }))
    return { success: true }
  }
  return { success: false, error: 'WebSocket 未连接' }
})

ipcMain.handle('stream:unsubscribe', async (_event, tsCodes: string[]) => {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    wsConnection.send(JSON.stringify({
      type: 'unsubscribe',
      ts_codes: tsCodes
    }))
    return { success: true }
  }
  return { success: false, error: 'WebSocket 未连接' }
})

ipcMain.handle('stream:get_status', async () => {
  return {
    success: true,
    data: {
      connected: wsConnection !== null && wsConnection.readyState === WebSocket.OPEN
    }
  }
})

// 应用退出时关闭 WebSocket
app.on('before-quit', () => {
  disconnectWebSocket()
})
