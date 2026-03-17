import logging
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from database import get_db
from models import Account, Transaction, LedgerEntry

logger=logging.getLogger(__name__)

router = APIRouter(tags=["Cỏe Banking"])

#SCHEMAS
class AccountCreate(BaseModel): 
    owner_name: str

class DepositRequest(BaseModel):
    account_id: uuid.UUID
    amount: Decimal = Field(gt=0, decimal_places=2, description="Deposit amount must be greater than zero")

# Pydantic models for request/response validation
class TransferRequest(BaseModel):
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    amount: Decimal = Field(gt=0, decimal_places=2, description="Transfer amount must be greater than zero")

async def get_balance(db: AsyncSession, account_id: uuid.UUID) -> Decimal: 
    #credit 
    credit_stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.account_id == account_id,
        LedgerEntry.entry_type == "credit"
    )

    #debit
    debit_stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.account_id == account_id,
        LedgerEntry.entry_type == "debit"
    )

    total_credit=(await db.execute(credit_stmt)).scalar()
    total_debit=(await db.execute(debit_stmt)).scalar()

    return total_credit - total_debit

@router.post("/accounts") 
async def create_account(request: AccountCreate, db: AsyncSession = Depends(get_db)):
    try:    
        new_account = Account(owner_name=request.owner_name)
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)
        logger.info(f"Created new account with ID: {new_account.id} for owner: {new_account.owner_name}")
        return {"account_id": new_account.id, "owner_name": new_account.owner_name}

    except Exception as e:
        logger.error(f"Error creating account: {str(e)}, exc_info=True")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/deposit")
async def deposit_funds(request: DepositRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"Request to deposit {request.amount} to account {request.account_id}")
    try:
        async with db.begin():
            stmt = select(Account).where(Account.id == request.account_id)
            account = (await db.execute(stmt)).scalar_one_or_none()

            if not account:
                logger.warning(f"Account {request.account_id} not found for deposit")
                raise HTTPException(status_code=404, detail="Account not found")
            new_txn = Transaction(
                sender_id=request.account_id, reveiver_id=request.account_id, amount=request.amount, status="completed"
            )
            db.add(new_txn)
            await db.flush()

            credit_entry = LedgerEntry(
                transaction_id=new_txn.id, account_id=request.account_id, amount=request.amount, entry_type="credit"
            )
            db.add(credit_entry)
        logger.info(f"Deposit of {request.amount} to account {request.account_id} successful, transaction ID: {new_txn.id}")
        return {"message": "Deposit successful", "transaction_id": new_txn.id}
    except Exception as e:
        logger.error(f"Error depositing funds: {str(e)}, exc_info=True")
        raise HTTPException(status_code=500, detail="Internal Server Error")

#API transfer endpoint
@router.post("/transfer")
async def transfer_funds(request: TransferRequest, db: AsyncSession = Depends(get_db)):
    if request.sender_id == request.receiver_id:
        raise HTTPException(status_code=400, detail="Sender and receiver cannot be the same")

    #open DB transaction
    async with db.begin():
        # 1. Pessimistic locking - lock sender and receiver accounts to prevent concurrent modifications
        sender_stmt = select(Account).where(Account.id == request.sender_id).with_for_update()
        sender = (await db.execute(sender_stmt)).scalar_one_or_none()

        if not sender:
            raise HTTPException(status_code=404, detail="Sender account not found")

        # 2. Check receiver account 
        receiver_stmt = select(Account).where(Account.id == request.receiver_id).with_for_update()
        receiver = (await db.execute(receiver_stmt)).scalar_one_or_none()

        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver account not found")

        # 3. Cal balance after locking accounts to ensure accuracy in concurrent scenarios
        current_balance = await get_balance(db, request.sender_id)
        if current_balance < request.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        # 4. transaction 
        new_txn = Transaction(
            sender_id=request.sender_id,
            receiver_id=request.receiver_id,
            amount=request.amount,
            status="completed"
        )        

        db.add(new_txn)
        await db.flush()  # Ensure transaction ID is generated

        # 5. ledger entries
        debit_entry = LedgerEntry(
            transaction_id=new_txn.id,
            account_id=request.sender_id,
            amount=request.amount,
            entry_type="debit"
        )
        credit_entry = LedgerEntry(
            transaction_id=new_txn.id,
            account_id=request.receiver_id,
            amount=request.amount,
            entry_type="credit"
        )
        db.add([debit_entry, credit_entry]) 

    return {"message": "Transfer successful", "transaction_id": new_txn.id}