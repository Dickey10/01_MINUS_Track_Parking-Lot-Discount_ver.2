from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["super_admin", "division_admin", "user", "inactive"]
ApplicationStatus = Literal["pending", "processing", "succeeded", "failed", "manual"]
EmailStatus = Literal["not_sent", "sent", "failed"]


class LoginRequest(BaseModel):
    username: str
    password: str


class AccountCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    division: str = ""
    department: str = ""
    role: Role = "user"
    is_active: bool = True


class AccountUpdate(BaseModel):
    display_name: str | None = None
    division: str | None = None
    department: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DivisionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class EmailRecipientCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str = ""
    is_active: bool = True


class ParkingApplicationCreate(BaseModel):
    car_number: str = Field(min_length=2, max_length=30)
    entry_time: datetime | None = None
    dept: str = Field(min_length=1, max_length=80)
    requester: str = Field(min_length=1, max_length=80)
    visitor_company: str = ""
    visit_purpose: str = Field(min_length=1, max_length=200)
    auto_apply: bool = True


class ManualApplyRequest(BaseModel):
    reason: str = "Manual discount application"
    effective_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class RegisterRequest(BaseModel):
    car_number: str
    discount_type: Literal["30", "60"] = "30"
    coupon_30_count: int = Field(default=0, ge=0, le=48)
    coupon_60_count: int = Field(default=0, ge=0, le=24)
    dept: str = ""
    requester: str = ""
    visitor_company: str = ""
    reason: str = ""


class RegisterResponse(BaseModel):
    success: bool
    message: str
    car_number: str
    discount_type: str = ""
    coupon_30_count: int = 0
    coupon_60_count: int = 0
    screenshot_path: str = ""
