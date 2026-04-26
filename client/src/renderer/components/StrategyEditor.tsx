import React, { useState } from 'react'
import { useAppStore, Condition } from '../store'

const CONDITION_TYPES = [
  { value: 'ma_cross', label: '均线交叉' },
  { value: 'kdj_cross', label: 'KDJ 交叉' },
  { value: 'macd_cross', label: 'MACD 交叉' },
  { value: 'price_break', label: '价格突破' }
]

export function StrategyEditor() {
  const { currentStrategy, setCurrentStrategy, strategies } = useAppStore()
  const [saving, setSaving] = useState(false)

  const addCondition = (type: Condition['type']) => {
    const defaultParams: Record<string, any> = {
      ma_cross: { fastMa: 5, slowMa: 20 },
      kdj_cross: { kThreshold: 20, dThreshold: 80 },
      macd_cross: {},
      price_break: { period: 20, direction: 'up' }
    }

    setCurrentStrategy({
      ...currentStrategy,
      conditions: [
        ...currentStrategy.conditions,
        { type, params: defaultParams[type], logic: 'AND' }
      ]
    })
  }

  const removeCondition = (index: number) => {
    setCurrentStrategy({
      ...currentStrategy,
      conditions: currentStrategy.conditions.filter((_, i) => i !== index)
    })
  }

  const updateConditionLogic = (index: number, logic: 'AND' | 'OR') => {
    const updated = [...currentStrategy.conditions]
    updated[index].logic = logic
    setCurrentStrategy({ ...currentStrategy, conditions: updated })
  }

  const handleSave = async () => {
    if (!currentStrategy.name.trim()) {
      alert('请输入策略名称')
      return
    }
    setSaving(true)
    try {
      const res = await window.api.strategy.save({
        name: currentStrategy.name,
        description: '',
        configJson: JSON.stringify(currentStrategy)
      })
      if (res.success) {
        alert('策略保存成功')
      } else {
        alert('保存失败: ' + res.error)
      }
    } catch (e: any) {
      alert('保存失败: ' + e.message)
    }
    setSaving(false)
  }

  return (
    <div className="strategy-editor">
      {/* 策略名称 */}
      <div style={{ marginBottom: '12px' }}>
        <input
          type="text"
          placeholder="策略名称"
          value={currentStrategy.name}
          onChange={(e) =>
            setCurrentStrategy({ ...currentStrategy, name: e.target.value })
          }
          style={{
            width: '100%',
            padding: '8px 12px',
            border: '1px solid #374151',
            borderRadius: '4px',
            background: '#1f2937',
            color: '#e0e6ed',
            fontSize: '13px'
          }}
        />
      </div>

      {/* 条件列表 */}
      <div className="condition-list">
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>
          信号触发条件
        </div>

        {currentStrategy.conditions.length === 0 && (
          <div style={{ color: '#4b5563', fontSize: '12px', padding: '8px' }}>
            暂无条件，点击下方按钮添加
          </div>
        )}

        {currentStrategy.conditions.map((c, i) => (
          <div key={i} className="condition-row">
            {i > 0 && (
              <select
                value={c.logic}
                onChange={(e) => updateConditionLogic(i, e.target.value as 'AND' | 'OR')}
                style={{ width: '60px', fontSize: '12px' }}
              >
                <option value="AND">且</option>
                <option value="OR">或</option>
              </select>
            )}

            <span style={{ flex: 1, fontSize: '12px', color: '#e0e6ed' }}>
              {CONDITION_TYPES.find((t) => t.value === c.type)?.label}:{' '}
              {JSON.stringify(c.params)}
            </span>

            <button
              onClick={() => removeCondition(i)}
              style={{
                padding: '2px 8px',
                fontSize: '11px',
                background: '#7f1d1d',
                color: '#ef4444',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer'
              }}
            >
              删除
            </button>
          </div>
        ))}
      </div>

      {/* 添加条件按钮 */}
      <div className="add-condition">
        {CONDITION_TYPES.map((ct) => (
          <button key={ct.value} onClick={() => addCondition(ct.value as Condition['type'])}>
            + {ct.label}
          </button>
        ))}
      </div>

      {/* 风控配置 */}
      <div className="risk-config">
        <h4>风控配置</h4>
        <div className="risk-row">
          <label>止损 %:</label>
          <input
            type="number"
            value={currentStrategy.risk.stopLoss}
            onChange={(e) =>
              setCurrentStrategy({
                ...currentStrategy,
                risk: { ...currentStrategy.risk, stopLoss: Number(e.target.value) }
              })
            }
          />
        </div>
        <div className="risk-row">
          <label>止盈 %:</label>
          <input
            type="number"
            value={currentStrategy.risk.takeProfit}
            onChange={(e) =>
              setCurrentStrategy({
                ...currentStrategy,
                risk: { ...currentStrategy.risk, takeProfit: Number(e.target.value) }
              })
            }
          />
        </div>
        <div className="risk-row">
          <label>每次买入金额:</label>
          <input
            type="number"
            value={currentStrategy.risk.positionSize}
            onChange={(e) =>
              setCurrentStrategy({
                ...currentStrategy,
                risk: { ...currentStrategy.risk, positionSize: Number(e.target.value) }
              })
            }
          />
        </div>
        <div className="risk-row">
          <label>单日最大交易次数:</label>
          <input
            type="number"
            value={currentStrategy.risk.maxDailyTrades}
            onChange={(e) =>
              setCurrentStrategy({
                ...currentStrategy,
                risk: { ...currentStrategy.risk, maxDailyTrades: Number(e.target.value) }
              })
            }
          />
        </div>
        <div className="risk-row">
          <label>最大持仓比例 %:</label>
          <input
            type="number"
            value={currentStrategy.risk.maxPositionRatio}
            onChange={(e) =>
              setCurrentStrategy({
                ...currentStrategy,
                risk: { ...currentStrategy.risk, maxPositionRatio: Number(e.target.value) }
              })
            }
          />
        </div>
      </div>

      {/* 保存按钮 */}
      <div className="save-strategy">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存策略'}
        </button>
      </div>
    </div>
  )
}
