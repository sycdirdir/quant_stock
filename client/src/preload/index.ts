import { contextBridge, ipcRenderer } from 'electron'

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
  }
}

contextBridge.exposeInMainWorld('api', api)

export type API = typeof api
