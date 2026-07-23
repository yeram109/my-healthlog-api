from datetime import date as date_type

from pydantic import field_validator
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
