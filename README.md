# 量化交易模拟平台

面向 **期货 + A 股投资者**的量化交易回测平台，支持日线/周线/月线数据回测、均线/MACD/KDJ 策略回测、时间轴播放模拟。

## 功能特性

- **K 线图表**：ECharts 蜡烛图 + MA5/MA10/MA20 均线叠加
- **均线交叉回测**：可视化配置策略条件，实时计算买卖信号
- **风控模块**：止损（5%）、止盈（10%）、仓位管理
- **回测指标**：收益率、夏普比率、最大回撤、胜率、盈亏比
- **策略管理**：策略模板保存/加载，云端同步（需服务端）
- **微信登录**：扫码认证（需微信开放平台资质）

## 项目结构

```
quant_stock/
├── client/                 # Windows 客户端（Electron + React）
│   ├── src/
│   │   ├── main/         # Electron 主进程
│   │   ├── preload/       # 预加载脚本
│   │   ├── renderer/      # React 渲染进程
│   │   │   ├── components/ # UI 组件
│   │   │   ├── store/    # Zustand 状态管理
│   │   │   └── styles/    # CSS 样式
│   │   └── python/        # Python 回测引擎
│   └── package.json
│
├── server/                # 后端服务（FastAPI）
│   ├── app/
│   │   ├── routers/       # API 路由（auth/stocks/data/cloud）
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic 模型
│   │   └── utils/         # JWT/JWT 工具
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── 量化交易模拟平台-需求文档.md
├── 量化交易模拟平台-系统设计文档.md
└── CLAUDE.md
```

---

## 快速部署

### 前置要求

- Python 3.11+
- Node.js 18+ / npm
- Docker（用于服务端部署）
- PostgreSQL 客户端（10.168.1.112，已导入 tushare 数据）

---

### 一、服务端部署（Docker）

```bash
cd server

# 配置环境变量（编辑 .env 或直接修改 docker-compose.yml）
# WECHAT_APPID / WECHAT_APPSECRET 留空可跳过微信登录

docker-compose up -d
```

服务启动后访问 `http://localhost:8000/docs` 查看 API 文档。

**手动启动（无 Docker）：**
```bash
cd server
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### 二、Windows 客户端开发

```bash
cd client

# 安装依赖
npm install

# 开发模式启动
npm run dev

# 打包 Windows 安装包
npm run package
```

> 客户端连接 `http://localhost:8000`（开发时）
> 打包后需修改主进程中的 API 地址指向实际服务器 IP

---

### 三、数据库连接

服务端连接 PostgreSQL（10.168.1.112 tushare 库）：

| 表名 | 说明 |
|------|------|
| `stock_basic` | 股票/期货基础信息（5493条） |
| `daily` | 日线数据（2020-01-02 ~ 2026-04-24） |
| `stock_weekly` | 周线数据 |
| `stock_monthly` | 月线数据 |

> 分钟线数据（1min/5min/30min/60min）待 H5 文件导入

---

## 环境变量

### 服务端（server/.env）

```env
DATABASE_URL=postgresql+asyncpg://user_PZW4Kp:password_6n6yfp@10.168.1.112:5432/tushare
JWT_SECRET=your_jwt_secret_key_here
WECHAT_APPID=your_wechat_appid
WECHAT_APPSECRET=your_wechat_appsecret
```

### 客户端（server 地址配置）

客户端默认连接 `http://localhost:8000`，修改 `client/src/main/index.ts` 中的 API 地址。

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/stocks` | GET | 股票列表（分页/搜索） |
| `GET /api/data/download/{ts_code}` | GET | K线数据下载 |
| `GET /api/data/updates` | GET | 增量更新列表 |
| `POST /api/auth/wechat/login` | POST | 微信登录 |
| `POST /api/cloud/strategies/sync` | POST | 策略云端同步 |

完整 API 文档：`http://localhost:8000/docs`

---

## 快速开始

1. 启动服务端：`cd server && docker-compose up -d`
2. 安装客户端依赖：`cd client && npm install`
3. 启动客户端：`cd client && npm run dev`
4. 登录（开发模式可跳过，直接进入主界面）
5. 选择股票 → 配置策略 → 运行回测
