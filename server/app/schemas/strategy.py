from pydantic import BaseModel
from typing import Optional, List, Any


class StrategyItem(BaseModel):
    local_id: int
    name: str
    description: Optional[str] = None
    config_json: str
    code: Optional[str] = None
    updated_at: Optional[str] = None


class StrategySyncRequest(BaseModel):
    strategies: List[StrategyItem]


class StrategySyncResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
