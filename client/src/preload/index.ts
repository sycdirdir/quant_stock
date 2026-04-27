import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

// 实时行情消息回调类型
type StreamCallback = (data: any) => void

// 回调存储
const streamCallbacks: Map<string, StreamCallback> = new Map()

// 监听渲染进程的实时行情消息
ipcRenderer.on('stream:message', (_event: IpcRendererEvent, message: any) => {
  streamCallbacks.forEach((callback) => callback(message))
})

ipcRenderer.on('stream:connected', (_event: IpcRendererEvent, data: any) => {
  streamCallbacks.forEach((callback) => callback({ type: 'connected', ...data }))
})

ipcRenderer.on('stream:disconnected', (_event: IpcRendererEvent, data: any) => {
  streamCallbacks.forEach((callback) => callback({ type: 'disconnected', ...data }))
})

// 暴露给渲染进程的 API
const api = {
  // 股票
  stocks: {
    list: (params: { page?: number; pageSize?: number; search?: string }) =>
      ipcRenderer.invoke('stocks:list', params)
  },

  // K线
  kline: {
    get: (params: { tsCode: string; period: string; startDate: string; endDate: string }) =>
      ipcRenderer.invoke('kline:get', params)
  },

  // 回测
  backtest: {
    run: (params: any) => ipcRenderer.invoke('backtest:run', params)
  },

  // 策略
  strategy: {
    save: (strategy: { name: string; description?: string; configJson: string; code?: string }) =>
      ipcRenderer.invoke('strategy:save', strategy),
    list: () => ipcRenderer.invoke('strategy:list')
  },

  // 数据
  data: {
    download: (params: { tsCode: string; period: string; startDate: string; endDate: string }) =>
      ipcRenderer.invoke('data:download', params)
  },

  // 认证
  auth: {
    wechatQr: () => ipcRenderer.invoke('auth:wechat_qr'),
    wechatLogin: (code: string) => ipcRenderer.invoke('auth:wechat_login', code)
  },

  // 实时行情 WebSocket
  stream: {
    connect: () => ipcRenderer.invoke('stream:connect'),
    disconnect: () => ipcRenderer.invoke('stream:disconnect'),
    subscribe: (tsCodes: string[]) => ipcRenderer.invoke('stream:subscribe', tsCodes),
    unsubscribe: (tsCodes: string[]) => ipcRenderer.invoke('stream:unsubscribe', tsCodes),
    getStatus: () => ipcRenderer.invoke('stream:get_status'),

    // 监听实时行情消息
    onMessage: (callback: StreamCallback) => {
      const id = Date.now().toString()
      streamCallbacks.set(id, callback)
      return () => streamCallbacks.delete(id) // 返回取消订阅函数
    }
  }
}

contextBridge.exposeInMainWorld('api', api)

export type API = typeof api
