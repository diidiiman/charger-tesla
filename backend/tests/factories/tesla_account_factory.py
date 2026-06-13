import factory
from app.models import TeslaAccount
from .user_factory import UserFactory
from datetime import datetime, timedelta, timezone


class TeslaAccountFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = TeslaAccount
        sqlalchemy_session_persistence = "commit"

    user = factory.SubFactory(UserFactory)
    access_token_enc = "encrypted_access_token"
    refresh_token_enc = "encrypted_refresh_token"
    access_token_expires_at = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    vehicle_id = factory.Faker("numerify", text="################")
    vehicle_vin = factory.Faker("bothify", text="5YJSA1E21H#######")
    vehicle_display_name = "Model S"
