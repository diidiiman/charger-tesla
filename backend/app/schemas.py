from datetime import datetime
from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=64)


class SessionToken(BaseModel):
    token: str
    user_id: int


class RegionInfo(BaseModel):
    code: str
    label: str


class UserSettings(BaseModel):
    region: str | None = None
    threshold_price: float | None = None
    currency: str = "EUR"
    auto_charge_enabled: bool = False


class UserSettingsUpdate(BaseModel):
    region: str | None = None
    threshold_price: float | None = None
    auto_charge_enabled: bool | None = None


class AuthStartResponse(BaseModel):
    authorize_url: str


class CallbackBody(BaseModel):
    callback_url: str


class CurrentPrice(BaseModel):
    region: str
    currency: str
    unit: str
    price: float
    valid_from: str
    valid_to: str
    provider: str


class DashboardResponse(BaseModel):
    settings: UserSettings
    tesla_linked: bool
    vehicle: dict | None = None
    price: CurrentPrice | None = None
    charge: dict | None = None
    subscription_active: bool


class SubscriptionSubmit(BaseModel):
    platform: str  # ios | android
    product_id: str
    receipt: str


class SubscriptionStatus(BaseModel):
    active: bool
    product_id: str | None
    expires_at: datetime | None
    platform: str | None
