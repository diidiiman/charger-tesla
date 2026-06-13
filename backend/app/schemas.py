from datetime import datetime
from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=64)


class SocialAuth(BaseModel):
    id_token: str
    device_id: str | None = None


class SocialAuth(BaseModel):
    id_token: str
    device_id: str | None = None


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
    vat_included: bool = True
    units: str = "metric"
    home_latitude: float | None = None
    home_longitude: float | None = None
    push_token: str | None = None
    price_change_reminder: bool = True
    auto_charge_enabled: bool = False


class UserSettingsUpdate(BaseModel):
    region: str | None = None
    threshold_price: float | None = None
    vat_included: bool | None = None
    units: str | None = None
    home_latitude: float | None = None
    home_longitude: float | None = None
    push_token: str | None = None
    price_change_reminder: bool | None = None
    auto_charge_enabled: bool | None = None


class AuthStartRequest(BaseModel):
    return_url: str | None = None


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


class TelemetryWebhookPayload(BaseModel):
    vehicle_id: str
    charging_state: str | None = None
    battery_level: int | None = None
    battery_range: float | None = None
    charger_power: float | None = None
    minutes_to_full_charge: int | None = None
    charge_limit_soc: int | None = None
    latitude: float | None = None
    longitude: float | None = None
