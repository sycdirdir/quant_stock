from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import auth, stocks, data, cloud

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="量化交易模拟平台 API",
    version="1.0.0",
    description="量化交易回测平台后端服务",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(data.router)
app.include_router(cloud.router)


@app.get("/")
async def root():
    return {"message": "量化交易模拟平台 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup():
    logger.info("量化交易模拟平台 API 启动成功")


@app.on_event("shutdown")
async def shutdown():
    logger.info("量化交易模拟平台 API 关闭")
