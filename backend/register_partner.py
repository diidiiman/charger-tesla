import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

CLIENT_ID = os.environ.get("TESLA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("TESLA_CLIENT_SECRET")
AUDIENCE = "https://fleet-api.prd.eu.vn.cloud.tesla.com"
AUTH_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
DOMAIN = os.environ.get("PUBLIC_DOMAIN", "api.charging.clankersystems.com")


async def main():
    headers = {"User-Agent": "TeslaCharger/1.0.0"}
    async with httpx.AsyncClient() as client:
        print("Fetching Partner Token...")
        # 1. Fetch Partner Token
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "audience": AUDIENCE,
            "scope": "openid vehicle_device_data vehicle_location vehicle_cmds vehicle_charging_cmds",
        }
        res = await client.post(AUTH_URL, data=data, headers=headers)
        if res.status_code >= 400:
            print("Failed to get partner token:", res.status_code, res.text)
            return

        token = res.json()["access_token"]
        print("Partner token retrieved.")

        print(f"Registering domain: {DOMAIN}")
        # 2. Register Partner Account
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "TeslaCharger/1.0.0",
        }
        reg_res = await client.post(
            f"{AUDIENCE}/api/1/partner_accounts",
            headers=auth_headers,
            json={"domain": DOMAIN},
        )

        print("Registration Status:", reg_res.status_code)
        print("Registration Response:", reg_res.text)


asyncio.run(main())
