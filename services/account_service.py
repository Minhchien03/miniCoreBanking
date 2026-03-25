import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from models import LedgerEntry, Account # Assuming Account is needed for type hinting or future use

async def get_balance(db: AsyncSession, account_id: uuid.UUID) -> Decimal:
    """
    Calculates the current balance for a given account by summing
    credit and debit entries from the LedgerEntry table.
    Optimized to a single query using SQL CASE and COALESCE.
    """
    stmt = select(
        func.coalesce(
            func.sum(
                case(
                    (LedgerEntry.entry_type == "credit", LedgerEntry.amount),
                    (LedgerEntry.entry_type == "debit", -LedgerEntry.amount),
                    else_=0
                )
            ),
            0
        )
    ).where(LedgerEntry.account_id == account_id)

    total_balance = (await db.execute(stmt)).scalar_one()
    return total_balance