from datetime import date as date_type

from pydantic import ValidationInfo, field_validator
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = False
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    is_admin: bool


class RecordBase(SQLModel):
    date: str
    weight: float = Field(ge=20, le=300)
    height: float = Field(ge=100, le=250)
    systolic: int = Field(ge=60, le=250)
    diastolic: int = Field(ge=30, le=150)
    blood_sugar: int = Field(ge=20, le=600)
    steps: int = Field(default=0, ge=0, le=100000)
    sleep_hours: float = Field(default=0.0, ge=0, le=24)
    memo: str = ""

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        try:
            parsed = date_type.fromisoformat(value)
        except ValueError:
            raise ValueError("date는 YYYY-MM-DD 형식이어야 합니다")
        if parsed.year < 1900:
            raise ValueError("1900년 이후 날짜만 입력 가능합니다")
        if parsed > date_type.today():
            raise ValueError("미래 날짜는 기록할 수 없습니다")
        return value

    @field_validator("diastolic")
    @classmethod
    def validate_diastolic_less_than_systolic(cls, value: int, info: ValidationInfo) -> int:
        systolic = info.data.get("systolic")
        if systolic is not None and value >= systolic:
            raise ValueError("이완기 혈압은 수축기 혈압보다 낮아야 합니다")
        return value


class Record(RecordBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")


class RecordCreate(RecordBase):
    pass


class RecordRead(RecordBase):
    id: int
    user_id: int
    bmi: float
    bmi_category: str
    bp_category: str
    sugar_category: str
    warnings: list[str]
    steps_grade: str
    sleep_category: str


class GoalBase(SQLModel):
    target_weight: float
    target_systolic: int
    target_diastolic: int


class Goal(GoalBase, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    set_date: str


class GoalCreate(GoalBase):
    pass
