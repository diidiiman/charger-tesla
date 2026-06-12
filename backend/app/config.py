from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    public_domain: str = "charging.clankersystems.com"

    database_url: str

    session_jwt_secret: str
    session_jwt_ttl_hours: int = 720

    token_encryption_key: str  # 64 hex chars (32 bytes)

    tesla_client_id: str = ""
    tesla_client_secret: str = ""
    tesla_redirect_uri: str = ""
    tesla_auth_base: str = "https://fleet-auth.prd.vn.cloud.tesla.com"
    tesla_api_base: str = "https://fleet-api.prd.eu.vn.cloud.tesla.com"

    mobile_deep_link_scheme: str = "teslacharger"

    price_provider: str = "nordpool"
    price_currency: str = "EUR"

    appstore_bundle_id: str = ""
    appstore_issuer_id: str = ""
    appstore_key_id: str = ""
    appstore_private_key_path: str = ""
    appstore_use_sandbox: bool = True

    play_package_name: str = ""
    play_service_account_json_path: str = ""

    scheduler_interval_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
