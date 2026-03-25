import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

from main import app

transport = ASGITransport(app=app, raise_app_exceptions=False)

@pytest.fixture
async def async_client():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_race_condition_transfer(async_client):
    """ 
    Proof: If there are 5 streams transferring money at the same time, the system only allows 1 successful stream. 
    To see Double Spending happen: Go to core_banking.py, delete function `.with_for_update()` 
    in the select(Account) line and then run this test again, the test will FAIL. 
    """
    # 1. Setup: create 2 accounts
    res_a = await async_client.post("/api/v1/accounts", json={"owner_name": "Xà C"})
    sender_id = res_a.json()["account_id"]
    
    res_b = await async_client.post("/api/v1/accounts", json={"owner_name": "Xà D"})
    receiver_id = res_b.json()["account_id"]

    # 2. deposits
    await async_client.post("/api/v1/deposit", json={"account_id": sender_id, "amount": 100})

    # 3. Attack scenario: Shoot 5 requests to transfer 100k AT THE SAME TIME (Concurrent)
    transfer_payload = {"sender_id": sender_id, "receiver_id": receiver_id, "amount": 100}
    
    # asyncio.gather will execute 5 requests at exactly 1 millisecond
    tasks = [async_client.post("/api/v1/transfer", json=transfer_payload) for _ in range(5)]
    responses = await asyncio.gather(*tasks)

    # 4. results
    success_count = sum(1 for res in responses if res.status_code == 200)
    failed_count = sum(1 for res in responses if res.status_code == 400) # Lỗi Insufficient funds

    # GUARANTEE: There is only 1 successful transaction, the remaining 4 transactions must be rejected
    assert success_count == 1, "Serious error: There was more than 1 successful withdrawal transaction!"
    assert failed_count == 4, "Error: Subsequent transactions are not blocked!"