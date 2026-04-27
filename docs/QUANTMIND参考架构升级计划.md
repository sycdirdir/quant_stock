# QuantMind 参考 — 架构升级计划

> 参考项目：https://github.com/qusong0627/QuantMind
> 整理日期：2026-04-27

---

## 一、QuantMind 架构核心亮点

### 1.1 微服务架构

```
Client (Electron/Web)
         │
         ▼
┌─────────────────────────────────────────┐
│           API Gateway (8000)              │
│   用户认证 | 策略管理 | 社区              │
└─────────────────────────────────────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Engine │ │ Trade  │ │ Stream │
│ :8001  │ │ :8002  │ │ :8003  │
│ 回测引擎│ │ 交易   │ │ 实时行情│
│ AI推理  │ │ 持仓   │ │ WebSocket│
│ 模型训练│ │ 风控   │ │        │
└────────┘ └────────┘ └────────┘
```

### 1.2 Qlib 回测引擎

微软开源量化框架，核心优势：
- **高性**能 Cython 实现，处理分钟线数据极快
- **Alpha158** 因子集（158维预计算因子）
- **LightGBM** 模型集成，端到端训练/推理
- **Backtest Loop** 事件驱动回测框架

### 1.3 双引擎回测

| 引擎 | 适用场景 | 性能 |
|------|----------|------|
| Qlib Engine | 多因子、机器学习策略 | 极高 |
| Pandas Engine | 简单策略、快速验证 | 轻量快速 |

### 1.4 AI 策略生成

- QuantBot 助手（对话生成策略）
- 一键模型训练
- 每日自动推理生成交易信号

### 1.5 完整风控体系

- 止损止盈
- 仓位管理
- 黑名单
- 异常预警
- 实时持仓监控

### 1.6 数据库架构

**Redis DB 分配（6个DB）：**
- DB0: 通用缓存
- DB1: 认证
- DB2: 交易
- DB3: 行情
- DB4: 回测
- DB5: 缓存

**PostgreSQL:**
- 用户/策略/交易记录
- 市场数据（含预计算因子）

---

## 二、我们系统的改进路线图

### P0 — 架构重构（立即开始）

#### 2.1 微服务拆分

**现状：** 单体 FastAPI（所有接口在一个进程）

**目标：** 4个服务，参考 QuantMind

```
client (Electron)
        │
        ▼
┌──────────────────────────────────────────┐
│         API Service (:8000)               │
│  认证 | 股票接口 | 策略 CRUD | 云同步     │
└──────────────────────────────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────────┐  ┌──────────┐
│ Engine   │  │ Stream   │
│ :8001    │  │ :8003    │
│ 回测引擎  │  │ 实时行情  │
│ Qlib集成 │  │ WebSocket│
└──────────┘  └──────────┘
```

**文件结构：**
```
server/
├── main_oss.py          # 统一入口
├── services/
│   ├── api/            # :8000 认证/策略/数据接口
│   ├── engine/         # :8001 回测引擎
│   └── stream/         # :8003 实时行情
├── shared/             # 共享模块
│   ├── config.py
│   ├── database.py
│   ├── redis_client.py
│   └── strategy_storage.py
├── docker-compose.yml
└── requirements.txt
```

#### 2.2 Qlib 集成

**安装：**
```bash
pip install qlib
```

**Qlib 数据初始化：**
```python
from qlib.data import D
from qlib.data.ops import Operators

# 初始化 Qlib
provider_uri = "/path/to/your/data"  # 本地数据路径
D.init(provider_uri=provider_uri)
```

**因子加载：**
```python
from qlib.data.ops import Operators

# 加载 Alpha158 因子（158维）
instruments = ["SH000001", "SZ000001"]
fields = ["$open", "$high", "$low", "$close", "$volume"] + [
    f"Ref($close, {i})" for i in range(1, 61)
]

df = D.features(instruments, fields, freq="day")
```

**Qlib Backtest Loop：**
```python
from qlib.backtest import Backtest, Strategy
from qlib.contrib.strategy import StrategyWrapper

class MyStrategy(Strategy):
    def generate(self, context):
        # 获取当前持仓
        position = context.get_position()
        # 获取信号
        signal = context.get_signal()
        # 下单逻辑
        ...

backtest = Backtest(
    strategy=MyStrategy(),
    recorder=recorder,
    account=100000,
    benchmark="SH000300"
)
```

### 2.3 数据库改进

**Redis 多 DB 配置：**
```python
import redis

class RedisManager:
    DB_GENERAL = 0
    DB_AUTH = 1
    DB_TRADE = 2
    DB_MARKET = 3
    DB_BACKTEST = 4
    DB_CACHE = 5

    def __init__(self):
        self.pool = redis.ConnectionPool(host='localhost', port=6379, max_connections=50)

    def get_client(self, db=0):
        return redis.Redis(connection_pool=self.pool, db=db)
```

**PostgreSQL 表扩展：**
```sql
-- 策略版本管理
CREATE TABLE strategy_versions (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    version INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    backtest_result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 持仓快照
CREATE TABLE position_snapshots (
    id SERIAL PRIMARY KEY,
    account_id INTEGER,
    ts_code VARCHAR(20),
    quantity DECIMAL(15,3),
    avg_price DECIMAL(10,3),
    snapshot_time TIMESTAMP NOT NULL
);

-- 交易信号记录
CREATE TABLE trading_signals (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER,
    ts_code VARCHAR(20),
    signal_type VARCHAR(10),  -- BUY/SELL
    signal_value DECIMAL(10,3),
    confidence DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.4 回测引擎双引擎

**Engine A: Pandas（简单策略）：**
```python
def pandas_backtest(data, strategy):
    """适合简单技术指标策略"""
    signals = detect_signals(data, strategy)
    trades = execute_trades(signals, initial_cash=100000)
    return calculate_metrics(trades)
```

**Engine B: Qlib（复杂策略）：**
```python
def qlib_backtest(instruments, strategy, start_date, end_date):
    """适合多因子、机器学习策略"""
    from qlib.workflow import R
    from qlib.contrib.strategy import SignalStrategy

    model = load_model("model.pkl")
    strategy = SignalStrategy(model=model)

    R.start(uri="sqlite:///history.db", experiment_name="backtest"):
        backtest = Backtest(
            strategy=strategy,
            start_time=start_date,
            end_time=end_date,
            account=100000,
            benchmark="SH000300"
        )
    return R.get_recorder().get_results()
```

---

### P1 — 核心功能增强

#### 3.1 因子库扩展

**基础技术指标（ta-lib）：**
```python
import talib

# KDJ
k, d = talib.STOCH(high, low, close, fastk_period=9,
                     slowk_period=3, slowk_matype=0)
j = 3 * k - 2 * d

# MACD
dif, dea, macd = talib.MACD(close, fastperiod=12,
                               slowperiod=26, signalperiod=9)

#布林带
upper, middle, lower = talib.BBANDS(close, timeperiod=20,
                                      nbdevup=2, nbdevdn=2)

# RSI
rsi = talib.RSI(close, timeperiod=14)
```

**Alpha158 因子（Qlib）：**
```python
from qlib.contrib.report import analysis_model

# 加载 158 维因子
fields = [
    "KLine_Close", "KLine_Open", "KLine_High", "KLine_Low",
    "KLine_Volume",
    # 动量因子
    "ROC5", "ROC10", "ROC20", "ROC60",
    # 波动率因子
    "Std20", "Std60",
    # 成交量因子
    "Volume_MA5", "Volume_MA20",
    # ... 共158维
]
```

#### 3.2 WebSocket 实时行情

**Stream Service：**
```python
from fastapi import WebSocket
from typing import Set

class StreamService:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

    async def push_quote(self, ts_code: str, quote: dict):
        await self.broadcast({
            "type": "quote",
            "ts_code": ts_code,
            "data": quote
        })
```

**客户端接收：**
```typescript
const ws = new WebSocket('ws://localhost:8003/stream')

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'quote') {
    updateKLine(data.ts_code, data.data)
  }
}
```

#### 3.3 风控中心增强

```python
class RiskControl:
    def __init__(self, config: dict):
        self.max_position_ratio = config.get('max_position_ratio', 0.3)
        self.max_single_loss = config.get('max_single_loss', 0.05)
        self.max_daily_loss = config.get('max_daily_loss', 0.1)
        self.blacklist = set(config.get('blacklist', []))

    def check_order(self, order: Order, position: Position, account: Account) -> bool:
        # 仓位检查
        if position.value / account.total_value > self.max_position_ratio:
            return False

        # 黑名单检查
        if order.ts_code in self.blacklist:
            return False

        # 单笔亏损检查
        if order.side == 'SELL' and position.unrealized_pnl < -self.max_single_loss * position.cost:
            return False

        return True

    def check_daily_loss(self, account: Account) -> bool:
        """当日亏损超限，强平所有持仓"""
        if account.daily_pnl < -self.max_daily_loss * account.initial_cash:
            return self.force_close_all()
        return False
```

---

### P2 — AI 增强（高级功能）

#### 4.1 LightGBM 模型训练

```python
import lightgbm as lgb
from qlib.contrib.model.gbdt import LGBModel

# 准备特征和标签
X_train, y_train = prepare_dataset(feature_df, label)
X_test, y_test = prepare_dataset(feature_df_test, label_test)

# 训练
model = lgb.train(
    params={
        "objective": "binary",
        "metric": "auc",
        "num_leaves": 31,
        "learning_rate": 0.05,
    },
    train_set=lgb.Dataset(X_train, y_train),
    valid_set=lgb.Dataset(X_test, y_test)
)

# 保存
model.save_model("model/lgb_model.txt")

# Qlib 集成
from qlib.contrib.model.gbdt import LGBModel
qlib_model = LGBModel()
qlib_model.load("model/lgb_model.txt")
```

#### 4.2 模型推理服务

```python
class InferenceService:
    def __init__(self, model_path: str):
        self.model = load_model(model_path)

    def predict(self, features: np.ndarray) -> dict:
        prob = self.model.predict(features)
        signal = "BUY" if prob > 0.6 else "SELL" if prob < 0.4 else "HOLD"
        return {
            "signal": signal,
            "confidence": abs(prob - 0.5) * 2,
            "probability": float(prob)
        }

    async def batch_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        features = self.extract_features(df)
        df["signal"] = self.model.predict(features)
        return df
```

#### 4.3 QuantBot 对话策略生成

```python
class QuantBot:
    def __init__(self):
        self.llm = LLM(provider="openai")

    def generate_strategy(self, description: str) -> dict:
        prompt = f"""
        用户想要一个量化策略："{description}"

        请生成策略配置（JSON格式）：
        {{
            "name": "策略名称",
            "conditions": [
                {{"type": "indicator", "params": {{}}}}
            ],
            "risk": {{}}
        }}
        """
        response = self.llm.complete(prompt)
        return json.loads(response)
```

---

## 三、部署架构升级

### Docker Compose（参考 QuantMind）

```yaml
version: '3.8'

services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - SERVICE_MODE=api
      - DB_HOST=postgres
      - REDIS_HOST=redis
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  engine:
    build: ./backend
    ports:
      - "8001:8001"
    environment:
      - SERVICE_MODE=engine
      - DB_HOST=postgres
      - REDIS_HOST=redis
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  stream:
    build: ./backend
    ports:
      - "8003:8003"
    environment:
      - SERVICE_MODE=stream
      - REDIS_HOST=redis
    depends_on:
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: quantmind
      POSTGRES_USER: quantmind
      POSTGRES_PASSWORD: quantmind123
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 四、优先级与工作量估算

| 阶段 | 功能 | 工作量 | 优先级 |
|------|------|--------|--------|
| **P0-1** | 微服务拆分（api/engine/stream） | 高 | 必须 |
| **P0-2** | Qlib 集成与 Pandas 双引擎 | 高 | 必须 |
| **P0-3** | Redis 多DB架构 | 中 | 必须 |
| **P1-1** | 因子库扩展（KDJ/MACD/布林带/RSI） | 中 | 重要 |
| **P1-2** | WebSocket 实时行情推送 | 中 | 重要 |
| **P1-3** | 风控中心增强 | 中 | 重要 |
| **P2-1** | LightGBM 模型训练 | 高 | 高级 |
| **P2-2** | QuantBot 对话策略生成 | 高 | 高级 |
| **P2-3** | 实盘 QMT 对接 | 高 | 高级 |

---

## 五、立即可执行的改进

基于现有代码，不需要大重构即可快速提升：

1. **回测引擎独立进程** — Python 子进程独立运行，不阻塞 UI
2. **因子库扩展** — 在 backtest_engine.py 中集成 ta-lib 计算 KDJ/MACD/布林带
3. **结果持久化** — 回测结果存入 PostgreSQL，支持历史对比
4. **信号标记** — 每次回测的买卖信号存入数据库，图表叠加显示
5. **数据预热** — Redis 缓存热点股票数据，加速切换
6. **Qlib 数据格式适配** — 将 PostgreSQL 数据导出为 Qlib 格式（ HDF5）

---

*文档参考来源：*
- *QuantMind GitHub: https://github.com/qusong0627/QuantMind*
- *Qlib 官方文档: https://qlib.readthedocs.io/*
