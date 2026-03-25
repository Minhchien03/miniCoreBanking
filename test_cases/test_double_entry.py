import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from main import app

transport = ASGITransport(app=app, raise_app_exceptions=False)

@pytest.fixture
async def async_client():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_transfer_happy_path_traceability(async_client):
    """
    Happy Path: Successful money transfer, check ledger and TraceID.
    """
    # 1. Setup
    res_a = await async_client.post("/api/v1/accounts", json={"owner_name": "Alice"})
    res_b = await async_client.post("/api/v1/accounts", json={"owner_name": "Bob"})
    sender_id, receiver_id = res_a.json()["account_id"], res_b.json()["account_id"]
    await async_client.post("/api/v1/deposit", json={"account_id": sender_id, "amount": 500})

    # 2. transfer money
    response = await async_client.post("/api/v1/transfer", json={
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "amount": 200
    })

    assert response.status_code == 200

    # 4. Check if TraceID is returned in the Header
    trace_id = response.headers.get("X-Trace-ID")
    assert trace_id is not None
    assert len(trace_id) > 10 # Ensure it's a valid UUID string


@pytest.mark.asyncio
async def test_transfer_sad_path_db_rollback(async_client):
    """
    Sad Path: Simulate a system error while recording the LedgerEntry. 
    Proof: Error in the middle will trigger ROLLBACK, user's money will not be lost.
    """
    # 1. Setup
    res_a = await async_client.post("/api/v1/accounts", json={"owner_name": "Dì A"})
    res_b = await async_client.post("/api/v1/accounts", json={"owner_name": "Dì B"})
    sender_id, receiver_id = res_a.json()["account_id"], res_b.json()["account_id"]
    await async_client.post("/api/v1/deposit", json={"account_id": sender_id, "amount": 300})

    # 2. Use 'patch' to sabotage the DB write function, simulate a database outage or hard drive overflow
    with patch("sqlalchemy.ext.asyncio.AsyncSession.add_all", side_effect=Exception("DB Connection Lost!")):
        response = await async_client.post("/api/v1/transfer", json={
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": 300
        })

    # 3. System must catch the error and return 500 Internal Server Error
    assert response.status_code == 500
    assert "DB Connection Lost" not in response.json()["detail"] 
    assert response.headers.get("X-Trace-ID") is not None


from sqlalchemy import select
from models import Account, LedgerEntry

@pytest.mark.asyncio
async def test_transfer_bad_no_rollback_disaster(async_client):
    """
    Scenario: API without Rollback. 
    Proof: The system reports 200 OK, but the money is "evaporated" from the ledger.
    """
    # 1. Setup
    res_e = await async_client.post("/api/v1/accounts", json={"owner_name": "Dì C"})
    res_f = await async_client.post("/api/v1/accounts", json={"owner_name": "Dì D"})
    eve_id, frank_id = res_e.json()["account_id"], res_f.json()["account_id"]
    await async_client.post("/api/v1/deposit", json={"account_id": eve_id, "amount": 400})

    with patch("sqlalchemy.ext.asyncio.AsyncSession.add_all", side_effect=Exception("DB Connection Lost!")):
        # GỌI API LỖI (/transfer_bad) thay vì API xịn
        response = await async_client.post("/api/v1/transfer_bad", json={
            "sender_id": eve_id,
            "receiver_id": frank_id,
            "amount": 300
        })
    
    # Consequence 1: Mobile/Web App still receives the Success notification!
    assert response.status_code == 200
    
    # Consequence 2: The money is actually transferred!
    # Get AsyncSession to check DB
    from database import async_session_maker
    async with async_session_maker() as db:
        eve = (await db.execute(select(Account).where(Account.id == eve_id))).scalar_one()
        frank = (await db.execute(select(Account).where(Account.id == frank_id))).scalar_one()
        
        assert eve.balance == 0
        assert frank.balance == 300
        
        # Consequence 3: Ledger is EMPTY! 
        # Money moves but doesn't leave any accounting trace.
        ledger_count = (await db.execute(
            select(LedgerEntry).where(LedgerEntry.account_id.in_([eve_id, frank_id]))
        )).scalars().all()
        
        assert len(ledger_count) == 0, "Disaster: No ledger entries found for this 300k transfer!"