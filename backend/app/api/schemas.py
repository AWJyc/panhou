from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _none_to_empty_list(v: Any) -> Any:
    return [] if v is None else v


_OptionalList = Annotated[list, BeforeValidator(_none_to_empty_list)]


class SectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    change_pct: float | None = None
    note: str = ""


class MoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str = ""
    name: str
    move_type: str
    change_pct: float | None = None
    note: str = ""
    limit_up_streak: int | None = None
    concept: str | None = None
    sealing_amount: float | None = None


class IndexOut(BaseModel):
    symbol: str
    name: str
    close: float | None = None
    change_pct: float | None = None


class ThemeOut(BaseModel):
    name: str
    narrative: str = ""
    members: list[str] = []


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market: str
    report_date: date
    summary_md: str
    generated_at: datetime
    model_used: str
    status: str
    sectors: Annotated[list[SectorOut], BeforeValidator(_none_to_empty_list)] = []
    movers: Annotated[list[MoverOut], BeforeValidator(_none_to_empty_list)] = []
    indices: Annotated[list[IndexOut], BeforeValidator(_none_to_empty_list)] = []
    themes: Annotated[list[ThemeOut], BeforeValidator(_none_to_empty_list)] = []


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market: str
    report_date: date
    status: str
