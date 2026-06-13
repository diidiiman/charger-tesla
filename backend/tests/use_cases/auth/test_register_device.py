import pytest
from app.use_cases.auth.register_device import RegisterDeviceUseCase
from app.models import User
from sqlalchemy import select


@pytest.mark.asyncio
async def test_register_device_creates_user(db_session):
    use_case = RegisterDeviceUseCase()
    device_id = "test-device-123"

    result = await use_case.call(db_session, device_id)

    assert result.token is not None
    assert result.user_id is not None

    user = (
        await db_session.execute(select(User).where(User.device_id == device_id))
    ).scalar_one_or_none()
    assert user is not None
    assert user.id == result.user_id


@pytest.mark.asyncio
async def test_register_device_returns_existing_user(db_session):
    use_case = RegisterDeviceUseCase()
    device_id = "test-device-123"

    result1 = await use_case.call(db_session, device_id)
    result2 = await use_case.call(db_session, device_id)

    assert result1.user_id == result2.user_id
