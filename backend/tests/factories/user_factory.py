import factory
from app.models import User
from datetime import datetime, timezone


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: n + 1)
    device_id = factory.Faker("uuid4")
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    region = "LV"
    threshold_price = 0.10
    currency = "EUR"
    vat_included = True
    units = "metric"
    home_latitude = 56.9
    home_longitude = 24.1
    push_token = None
    price_change_reminder = True
    auto_charge_enabled = False
