import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from database import get_db
from models import Account, Transaction, LedgerEntry
from schemas import AccountCreate, DepositRequest, TransferRequest
from exceptions import BusinessException
from services.account_service import get_balance
from middleware import trace_id_context # For accessing trace_id in logs
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Banking"])


@router.post("/accounts", summary="Create a new bank account")
async def create_account(
    request: AccountCreate, db: AsyncSession = Depends(get_db)
):
    """
    Creates a new bank account for a specified owner.
    """
    logger.info("Request to create account", extra={"owner_name": request.owner_name})

    new_account = Account(owner_name=request.owner_name)
    db.add(new_account)
    await db.commit()
    await db.refresh(new_account) # Refresh to get DB-generated fields like ID and created_at

    logger.info(
        "Account created successfully",
        extra={"account_id": new_account.id, "owner_name": new_account.owner_name}
    )

    return {"account_id": new_account.id, "owner_name": new_account.owner_name}


@router.post("/deposit", summary="Deposit funds into an account")
async def deposit_funds(
    request: DepositRequest, db: AsyncSession = Depends(get_db)
):
    """
    Deposits a specified amount into an existing account.
    Ensures atomicity using a database transaction.
    """
    logger.info(
        "Request to deposit funds",
        extra={"account_id": request.account_id, "amount": request.amount}
    )

    async with db.begin(): # Ensures ACID properties for the deposit operation
        # 1. Check if account exists
        # FIX: Corrected column name from ma_khach_hang_fake to id
        account = (
            await db.execute(select(Account).where(Account.id == request.account_id).with_for_update())
        ).scalar_one_or_none()

        if not account:
            logger.warning(
                "Account not found for deposit",
                extra={"account_id": request.account_id}
            )
            raise BusinessException(status_code=404, detail="Account not found")
        account.balance += request.amount  # Update balance in-memory; will be committed at the end of the transaction

        # 2. Create a new transaction record
        # For deposits, sender and receiver can be the same account, representing an internal credit.
        new_txn = Transaction(
            sender_id=request.account_id,
            receiver_id=request.account_id,
            amount=request.amount,
            status="completed",
        )
        db.add(new_txn)
        await db.flush()  # Flush to get the transaction ID for ledger entries

        # 3. Create a ledger entry for the credit
        credit_entry = LedgerEntry(
            transaction_id=new_txn.id,
            account_id=request.account_id,
            amount=request.amount,
            entry_type="credit",
        )
        db.add(credit_entry)
        # db.commit() is handled by async with db.begin() context manager

    logger.info(
        "Deposit successful",
        extra={"account_id": request.account_id, "amount": request.amount, "transaction_id": new_txn.id}
    )

    return {"message": "Deposit successful", "transaction_id": new_txn.id}


@router.post("/transfer", summary="Transfer funds between two accounts")
async def transfer_funds(
    request: TransferRequest, db: AsyncSession = Depends(get_db)
):
    """
    Transfers a specified amount from a sender account to a receiver account.
    Ensures atomicity and handles concurrency using pessimistic locking.
    """
    logger.info(
        "Request to transfer funds",
        extra={
            "sender_id": request.sender_id,
            "receiver_id": request.receiver_id,
            "amount": request.amount,
        }
    )

    if request.sender_id == request.receiver_id:
        logger.warning(
            "Transfer request with same sender and receiver",
            extra={"account_id": request.sender_id}
        )
        raise BusinessException(
            status_code=400,
            detail="Sender and receiver cannot be the same",
        )

    async with db.begin(): # Ensures ACID properties for the transfer operation
        # 1. Pessimistic locking - lock sender and receiver accounts 
        # This prevents race conditions during balance checks and updates.
        logger.debug(
            "Attempting to lock accounts for transfer",
            extra={"sender_id": request.sender_id, "receiver_id": request.receiver_id}
        )

        sender_stmt = (
            select(Account)
            .where(Account.id == request.sender_id)
            .with_for_update() # Locks the row - Pessimistic locking
        )
        sender = (await db.execute(sender_stmt)).scalar_one_or_none()

        if not sender:
            logger.warning(
                "Sender account not found for transfer",
                extra={"sender_id": request.sender_id}
            )
            raise BusinessException(
                status_code=404, detail="Sender account not found"
            )

        receiver_stmt = (
            select(Account)
            .where(Account.id == request.receiver_id)
            .with_for_update() # Locks the row
        )
        receiver = (await db.execute(receiver_stmt)).scalar_one_or_none()

        if not receiver:
            logger.warning(
                "Receiver account not found for transfer",
                extra={"receiver_id": request.receiver_id}
            )
            raise BusinessException(
                status_code=404, detail="Receiver account not found"
            )
        
        # Check balance account 
        if sender.balance < request.amount:
            logger.warning(
                "Insufficient funds for transfer",
                extra={
                    "sender_id": request.sender_id,
                    "current_balance": sender.balance,
                    "attempted_amount": request.amount,
                }
            )
            raise BusinessException(status_code=400, detail="Insufficient funds")
        
        await asyncio.sleep(0.1) # Simulate some processing delay to increase chance
        sender.balance -= request.amount  # Update sender balance in-memory
        receiver.balance += request.amount  # Update receiver balance in-memory

        # 3. Create a new transaction record
        new_txn = Transaction(
            sender_id=request.sender_id,
            receiver_id=request.receiver_id,
            amount=request.amount,
            status="completed",
        )
        db.add(new_txn)
        await db.flush()  # Flush to get the transaction ID for ledger entries

        # 4. Create ledger entries for debit (sender) and credit (receiver)
        debit_entry = LedgerEntry(
            transaction_id=new_txn.id,
            account_id=request.sender_id,
            amount=request.amount,
            entry_type="debit",
        )

        credit_entry = LedgerEntry(
            transaction_id=new_txn.id,
            account_id=request.receiver_id,
            amount=request.amount,
            entry_type="credit",
        )

        db.add_all([debit_entry, credit_entry])
        # db.commit() is handled by async with db.begin() context manager

    logger.info(
        "Transfer successful",
        extra={
            "sender_id": request.sender_id,
            "receiver_id": request.receiver_id,
            "amount": request.amount,
            "transaction_id": new_txn.id,
        }
    )

    return {"message": "Transfer successful", "transaction_id": new_txn.id}


#giả lập không rollback được, để test rollback tự động của SQLAlchemy khi lỗi xảy ra giữa chừng
@router.post("/transfer_bad", summary="BAD API - Cố tình không có Rollback để Demo cho sếp")
async def transfer_funds_bad(
    request: TransferRequest, db: AsyncSession = Depends(get_db)
):
    """
    API này mô phỏng một lập trình viên quên dùng transaction block.
    Số dư được lưu thẳng vào DB ngay lập tức. Nếu ghi sổ cái lỗi, hệ thống ngó lơ luôn!
    """
    # 1. Đọc tài khoản (Bỏ qua check null cho code ngắn gọn)
    sender = (await db.execute(select(Account).where(Account.id == request.sender_id))).scalar_one()
    receiver = (await db.execute(select(Account).where(Account.id == request.receiver_id))).scalar_one()

    # 2. TRỪ TIỀN VÀ LƯU NGAY LẬP TỨC (Lỗi chết người ở đây)
    sender.balance -= request.amount
    receiver.balance += request.amount
    await db.commit() # Dữ liệu được chốt hạ vào ổ cứng!

    # 3. Cố gắng ghi Sổ cái (Ledger)
    try:
        # Tạo fake transaction id cho nhanh
        fake_txn_id = uuid.uuid4() 
        debit_entry = LedgerEntry(transaction_id=fake_txn_id, account_id=request.sender_id, amount=request.amount, entry_type="debit")
        credit_entry = LedgerEntry(transaction_id=fake_txn_id, account_id=request.receiver_id, amount=request.amount, entry_type="credit")
        
        db.add_all([debit_entry, credit_entry])
        await db.commit()
    except Exception as e:
        logger.error("Đứt mạng khi ghi sổ cái! NHƯNG lờ đi và vẫn báo thành công!")
        # ĐÁNG LẼ PHẢI ROLLBACK, NHƯNG LẠI KHÔNG LÀM GÌ CẢ VÀ CHO QUA!

    # 4. Trả về thành công ảo
    return {"message": "Transfer successful (but ledger is completely broken!)"}