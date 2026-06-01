from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, constr
from datetime import datetime


class StatusEnum(str, Enum):
    HEALTHY = "HEALTHY"
    NOT_HEALTHY = "NOT_HEALTHY"


class HealthResponse(BaseModel):
    status: StatusEnum
    details: Dict[str, Any]
    timestamp: datetime


# Beam line models
NonEmptyStr = constr(min_length=1)


class BeamLineCreate(BaseModel):
    name: NonEmptyStr = Field(..., alias="Name")
    description: Optional[str] = Field(None, alias="Description")


class BeamLineUpdate(BaseModel):
    name: Optional[NonEmptyStr] = Field(None, alias="Name")
    description: Optional[str] = Field(None, alias="Description")


class BeamLineData(BaseModel):
    id: int = Field(..., alias="ID")
    name: str = Field(..., alias="Name")
    description: Optional[str] = Field(None, alias="Description")


class LinksModel(BaseModel):
    line_items: str = Field(..., alias="Line_items")


class BeamLineDetailResponse(BaseModel):
    links: LinksModel = Field(..., alias="Links")
    data: BeamLineData = Field(..., alias="Data")


class BeamLineListResponse(BaseModel):
    page: int = Field(..., alias="Page")
    per_page: int = Field(..., alias="Per_page")
    total: int = Field(..., alias="Total")
    data: List[BeamLineData] = Field(..., alias="Data")
