import pytest
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_register_device_route(client):
    response = await client.post(
        "/v1/auth/device", json={"device_id": "route-device-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_register_device_route_invalid(client):
    response = await client.post("/v1/auth/device", json={"device_id": "short"})
    assert response.status_code == 422
