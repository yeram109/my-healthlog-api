from datetime import date as date_type

from pydantic import BaseModel, field_validator


class RecordIn(BaseModel):
    date: str
    weight: float
    height: float
    systolic: int
    diastolic: int
    blood_sugar: int
    steps: int = 0
    sleep_hours: float = 0.0
    memo: str = ""

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        try:
            date_type.fromisoformat(value)
        except ValueError:
            raise ValueError("date는 YYYY-MM-DD 형식이어야 합니다")
        return value


class RecordOut(RecordIn):
    id: int
    user: str
    bmi: float
    bmi_category: str
    bp_category: str
    sugar_category: str
    warnings: list[str]


class GoalIn(BaseModel):
    target_weight: float
    target_systolic: int
    target_diastolic: int
