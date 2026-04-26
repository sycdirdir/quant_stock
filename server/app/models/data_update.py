from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class DataUpdateRecord(Base):
    __tablename__ = "data_update_records"

    id = Column(Integer, primary_key=True, index=True)
    update_date = Column(String(10), nullable=False, index=True)  # YYYYMMDD
    updated_stocks = Column(Text)  # JSON array
    version = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())
