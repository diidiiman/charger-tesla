import pytest
from app.models import User
from tests.factories.user_factory import UserFactory
from tests.factories.tesla_account_factory import TeslaAccountFactory


@pytest.mark.asyncio
async def test_get_regions(client):
    response = await client.get("/v1/regions")
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.asyncio
async def test_get_settings_unauthorized(client):
    response = await client.get("/v1/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_authorized(client, db_session, create_auth_headers):
    user = UserFactory.build()
    db_session.add(user)
    await db_session.commit()

    headers = create_auth_headers(user.id)
    response = await client.get("/v1/settings", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["region"] == "LV"


@pytest.mark.asyncio
async def test_update_settings(client, db_session, create_auth_headers):
    user = UserFactory.build()
    db_session.add(user)
    await db_session.commit()

    headers = create_auth_headers(user.id)
    response = await client.put(
        "/v1/settings", headers=headers, json={"region": "NO1", "threshold_price": 0.15}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["region"] == "NO1"
    assert data["threshold_price"] == 0.15
