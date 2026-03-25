import uuid
from decimal import Decimal
from pydantic import BaseModel, Field

# SCHEMAS
class AccountCreate(BaseModel):
    owner_name: str = Field(..., min_length=1, description="Name of the account owner")


class DepositRequest(BaseModel):
    account_id: uuid.UUID
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Deposit amount must be greater than zero and have up to 2 decimal places",
    )


class TransferRequest(BaseModel):
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Transfer amount must be greater than zero and have up to 2 decimal places",
    )