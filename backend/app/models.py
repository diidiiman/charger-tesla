from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Stable device id from the mobile install (UUID). One user per device for v1.
    device_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    google_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    apple_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    region: Mapped[str | None] = mapped_column(String(16), nullable=True)
    threshold_price: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False)
    vat_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    units: Mapped[str] = mapped_column(String(16), default="metric", nullable=False)
    home_latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    home_longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price_change_reminder: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    auto_charge_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    tesla: Mapped["TeslaAccount | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class TeslaAccount(Base):
    __tablename__ = "tesla_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Tokens are AES-256-GCM encrypted blobs (base64).
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    vehicle_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vehicle_vin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vehicle_display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="tesla")


class Subscription(Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    platform: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'ios' | 'android'
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Raw receipt / purchase token for re-verification.
    receipt: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="subscription")


class OAuthState(Base):
    """PKCE verifier + nonce stash for the in-flight OAuth code exchange."""

    __tablename__ = "oauth_states"
    __table_args__ = (UniqueConstraint("state"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RegionPrice(Base):
    """Stores hourly electricity prices per region."""

    __tablename__ = "region_prices"
    __table_args__ = (UniqueConstraint("region", "valid_from"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    price_with_vat: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChargeEvent(Base):
    """Audit trail of auto-charge actions for subscribed users."""

    __tablename__ = "charge_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'start' | 'stop' | 'skip'
    price: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    threshold: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
