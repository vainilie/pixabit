import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://habitica.com/api/v3"
HEADERS = {
    "x-api-user": os.getenv("HABITICA_USER_ID"),
    "x-api-key": os.getenv("HABITICA_API_TOKEN"),
    "Content-Type": "application/json",
}

client = httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS)

async def fetch_user_tasks():
    response = await client.get("/tasks/user")
    response.raise_for_status()
    return response.json()["data"]

