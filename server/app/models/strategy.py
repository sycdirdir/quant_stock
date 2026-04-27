"""
策略模型
用于策略云端同步和版本管理
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Strategy(Base):
    """策略表"""
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    config_json = Column(Text, nullable=False)  # 策略配置 JSON
    code = Column(Text)  # Python 代码 (可选)
    is_public = Column(Boolean, default=False)  # 是否公开策略

    # 版本管理
    version = Column(Integer, default=1)

    # 同步状态
    synced = Column(Boolean, default=False)
    last_synced_at = Column(DateTime)

    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StrategyVersion(Base):
    """策略版本表 - 保存历史版本"""
    __tablename__ = "strategy_versions"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config_json = Column(Text, nullable=False)
    backtest_result_json = Column(Text)  # 回测结果 JSON
    changelog = Column(Text)  # 版本变更说明

    created_at = Column(DateTime, server_default=func.now())


class StrategyTemplate(Base):
    """策略模板表 - 公开模板"""
    __tablename__ = "strategy_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # 趋势/震荡/套利
    config_json = Column(Text, nullable=False)
    author = Column(String(100))

    # 使用统计
    use_count = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
