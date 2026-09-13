from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class AcusByProduct(BaseModel):
    devin: float = 0.0
    cascade: float = 0.0
    terminal: float = 0.0
    review: float | None = None


class ConsumptionByDate(BaseModel):
    date: int
    acus: float
    acus_by_product: AcusByProduct = Field(default_factory=AcusByProduct)


class ConsumptionResponse(BaseModel):
    total_acus: float
    consumption_by_date: list[ConsumptionByDate] = Field(default_factory=list)


@dataclass
class ConsumptionUnavailable:
    reason: str
    status_code: int | None = None


def parse_consumption_response(data: dict[str, Any]) -> ConsumptionResponse:
    return ConsumptionResponse.model_validate(data)
