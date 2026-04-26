import React, { useState } from 'react'
import { useAppStore } from '../store'

export function LoginScreen() {
  const { setUser, setJwtToken } = useAppStore()
  const [loading, setLoading] = useState(false)
  const [sceneStr] = useState(() => Math.random().toString(36).slice(2))

  const handleLogin = async () => {
    setLoading(true)
    // 模拟登录成功（实际需要微信扫码）
    setTimeout(() => {
      setUser({ user_id: 'mock_user_001', nickname: '量化用户', avatar_url: '' })
      setJwtToken('mock_jwt_token_' + Date.now())
      setLoading(false)
    }, 1000)
  }

  return (
    <div className="login-overlay">
      <div className="login-box">
        <h2>量化交易模拟平台</h2>
        <p>请使用微信扫码登录</p>

        <div className="qr-placeholder">
          微信扫码区域
          <br />
          (scene: {sceneStr})
        </div>

        <button
          className="btn btn-primary"
          style={{ width: '100%' }}
          disabled={loading}
          onClick={handleLogin}
        >
          {loading ? '登录中...' : '模拟登录（开发模式）'}
        </button>
      </div>
    </div>
  )
}
